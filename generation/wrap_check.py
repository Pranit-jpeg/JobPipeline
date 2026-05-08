"""Render-feedback wrap detection + fix.

LLMs cannot reliably count characters, and character thresholds don't map
cleanly to line wraps (capacity depends on tightness level + word boundaries).
This module solves the problem by parsing the *rendered* PDF, finding bullets
whose last line is mostly empty, and asking the model to rewrite — grounded
in the actual rendered output.

Usage:
    from generation.wrap_check import remediate_wraps_with_render_feedback

The detection uses last-line-fill ratio relative to the first line of the
same bullet (the bullet's first line is always max-width because the docx
writer pushes text until wrap). A ratio below ~0.65 means the second line is
mostly white space — what the user has flagged as ugly.
"""

import json
import logging
import re
from typing import Optional

import anthropic
from pypdf import PdfReader

_log = logging.getLogger(__name__)

# Possible bullet markers. docx_writer.py uses "– " (U+2013). pypdf may render
# the same character or substitute. We match conservatively.
_BULLET_PREFIXES = ("– ", "— ", "- ", "– ", "— ")

_SECTION_HEADERS = {
    "PROFESSIONAL SUMMARY", "WORK EXPERIENCE", "EDUCATION",
    "ACADEMIC PROJECTS", "SKILLS",
}

# Date-range pattern e.g. "Sep 2025 – Dec 2025" or "Sep 2025 - Dec 2025"
_DATE_RANGE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{4}\b"
)


class BulletRender:
    def __init__(self, lines: list[str]):
        self.lines = [l for l in lines if l.strip()]
        self.text = " ".join(self.lines)
        self.n_lines = len(self.lines)
        self.line_chars = [len(l) for l in self.lines]
        self.first_line_chars = self.line_chars[0] if self.lines else 0
        self.last_line_chars = self.line_chars[-1] if self.lines else 0
        if self.n_lines >= 2 and self.first_line_chars > 0:
            self.fill_ratio = self.last_line_chars / self.first_line_chars
        else:
            # Single-line bullet: trivially "filled"
            self.fill_ratio = 1.0

    def is_bad_wrap(self, threshold: float) -> bool:
        return self.n_lines >= 2 and self.fill_ratio < threshold

    def __repr__(self):
        return (
            f"BulletRender(n_lines={self.n_lines}, "
            f"fill={self.fill_ratio:.2f}, "
            f"text={self.text[:50]!r})"
        )


def _starts_with_bullet(line: str) -> bool:
    s = line.lstrip()
    return any(s.startswith(p) for p in _BULLET_PREFIXES)


def _strip_bullet_prefix(line: str) -> str:
    s = line.lstrip()
    for p in _BULLET_PREFIXES:
        if s.startswith(p):
            return s[len(p):].rstrip()
    return s.rstrip()


def _is_company_or_degree_header(line: str) -> bool:
    return bool(_DATE_RANGE_RE.search(line))


def extract_rendered_bullets(pdf_path: str) -> list[BulletRender]:
    """Parse the resume PDF and return one BulletRender per bullet.

    Bullets are walked top-to-bottom and terminated by:
      - a new bullet line (starts with the bullet marker)
      - a section header (ALL CAPS line in the known section list)
      - a company/degree header (line containing a month-year date)

    Continuation lines are accumulated into the current bullet.
    """
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() for page in reader.pages)

    bullets: list[BulletRender] = []
    current: Optional[list[str]] = None

    def _flush():
        nonlocal current
        if current:
            bullets.append(BulletRender(current))
            current = None

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        # Section header
        if stripped.upper() in _SECTION_HEADERS:
            _flush()
            continue

        # Bullet start
        if _starts_with_bullet(line):
            _flush()
            current = [_strip_bullet_prefix(line)]
            continue

        # Company/degree header — terminates current bullet
        if _is_company_or_degree_header(stripped):
            _flush()
            continue

        # Continuation line for the current bullet
        if current is not None:
            current.append(stripped)

    _flush()
    return bullets


def find_bad_wraps(
    bullets: list[BulletRender], threshold: float = 0.65
) -> list[BulletRender]:
    """Return bullets whose last line is < threshold × first line."""
    return [b for b in bullets if b.is_bad_wrap(threshold)]


# ── Mapping rendered bullets back to resume_data ─────────────────────────────

def _norm(s: str) -> str:
    """Whitespace-normalize for fuzzy matching across slight rendering diffs."""
    return re.sub(r"\s+", " ", s).strip().lower()


def locate_in_resume(rendered: BulletRender, resume_data: dict) -> Optional[tuple]:
    """Find which bullet in resume_data corresponds to this rendered bullet.

    Returns (group, group_idx, bullet_idx, original_text) or None.
    Uses normalized exact match first, then a length-aware prefix match.
    """
    target = _norm(rendered.text)

    # Exact (normalized) match
    for j_idx, job in enumerate(resume_data.get("work_experience", [])):
        for b_idx, bullet in enumerate(job.get("bullets", [])):
            if _norm(bullet) == target:
                return ("work_experience", j_idx, b_idx, bullet)
    for p_idx, proj in enumerate(resume_data.get("academic_projects", [])):
        for b_idx, bullet in enumerate(proj.get("bullets", [])):
            if _norm(bullet) == target:
                return ("academic_projects", p_idx, b_idx, bullet)

    # Prefix match (in case pypdf trimmed/joined differently)
    prefix = target[: min(40, len(target))]
    for j_idx, job in enumerate(resume_data.get("work_experience", [])):
        for b_idx, bullet in enumerate(job.get("bullets", [])):
            if _norm(bullet).startswith(prefix):
                return ("work_experience", j_idx, b_idx, bullet)
    for p_idx, proj in enumerate(resume_data.get("academic_projects", [])):
        for b_idx, bullet in enumerate(proj.get("bullets", [])):
            if _norm(bullet).startswith(prefix):
                return ("academic_projects", p_idx, b_idx, bullet)

    return None


# ── End-to-end fix routine ──────────────────────────────────────────────────

_FIX_MODEL = "claude-opus-4-7"
_FIX_MAX_TOKENS = 3000


def remediate_wraps_with_render_feedback(
    resume_data: dict,
    pdf_path: str,
    base_resume_text: str,
    client: anthropic.Anthropic,
    fill_threshold: float = 0.50,
) -> tuple[dict, list[str]]:
    """Detect bullets in the rendered PDF whose last line is < fill_threshold
    of the first line, and ask the model to rewrite each. Apply fixes in place.

    Returns (resume_data, audit_lines). Audit lines describe what was found
    and what was changed; surface them in the dashboard.
    """
    audit: list[str] = []
    try:
        rendered = extract_rendered_bullets(pdf_path)
    except Exception as e:
        audit.append(f"Render-feedback wrap check: PDF parse failed ({e}). Skipped.")
        return resume_data, audit

    bad_pairs: list[tuple[BulletRender, tuple]] = []
    for r in rendered:
        if not r.is_bad_wrap(fill_threshold):
            continue
        loc = locate_in_resume(r, resume_data)
        if loc is None:
            audit.append(
                f"Render-feedback: bullet '{r.text[:50]}…' "
                f"(fill {r.fill_ratio:.0%}) couldn't be matched back to source — skipped."
            )
            continue
        bad_pairs.append((r, loc))

    if not bad_pairs:
        audit.append(
            f"Render-feedback wrap check: all multi-line bullets have last-line fill "
            f"≥ {fill_threshold:.0%}. No fixes needed."
        )
        return resume_data, audit

    # Build a prompt that tells the model EXACTLY what the rendered output looks
    # like. Each bullet has its current text + its measured render state.
    # Target a moderate fill (65%) — enough to escape "obviously empty" but
    # without over-expanding, which would force the auto-fit into very tight
    # tightness levels.
    target_fill = 0.65
    bullets_block = ""
    for i, (r, loc) in enumerate(bad_pairs):
        _g, _gi, _bi, original = loc
        bullets_block += (
            f"\n[{i+1}] CURRENT TEXT ({len(original)} chars):\n"
            f"    {original}\n"
            f"    RENDERS AS {r.n_lines} lines:\n"
            f"      • Line 1 ({r.first_line_chars} chars): {r.lines[0]!r}\n"
        )
        for j, ln in enumerate(r.lines[1:-1], start=2):
            bullets_block += f"      • Line {j} ({len(ln)} chars): {ln!r}\n"
        bullets_block += (
            f"      • Line {r.n_lines} ({r.last_line_chars} chars): {r.lines[-1]!r}  ← LAST LINE\n"
            f"    LINE 1 vs LAST LINE FILL: {r.fill_ratio:.0%}  ← BAD (line {r.n_lines} is mostly empty)\n"
        )

    prompt = f"""The user's resume just rendered to PDF. {len(bad_pairs)} bullet(s) wrap to multiple lines but the last line is mostly empty (less than {int(fill_threshold*100)}% as long as the first line), leaving ugly white space on the page.

**Your job: make each bad bullet's last line at least {int(target_fill*100)}% as long as its first line — but DO NOT over-expand.**

The way to fix is to ADD a small amount of detail back from the base resume — a specific number, method, tool, dataset, deliverable, or context that the current tailored version dropped during tailoring. Just enough to escape the visibly-empty zone. Stop when you reach ~{int(target_fill*100)}% fill.

Constraints:
- DO NOT over-expand. The user has explicitly complained about bullets so long they force the resume into very tight font levels. Add the MINIMUM detail needed to clear ~{int(target_fill*100)}% fill. Do not maximize content.
- The rewrite must keep the bullet's core claim intact.
- Add ONLY detail that already exists in the base resume. NEVER fabricate numbers, projects, tools, or facts.
- Stay under 230 characters total. Anything above wraps to 3 lines.
- Look at "Line 1" in the rendered output below — that's roughly your line capacity. The new bullet's last line should reach ~{int(target_fill*100)}% of that, not more.

**Default: expand modestly to reach ~{int(target_fill*100)}% fill.** Adding too little leaves the bullet looking empty; adding too much forces the resume into a tight font.

ONLY if the base resume has no more meaningful detail to add, may you rewrite the bullet to fit on a single line (~120 chars). This should be rare — most bullets dropped detail during tailoring that can be restored.

BASE RESUME (use to find detail that was dropped):
---
{base_resume_text}
---

BULLETS TO FIX (with their current rendered state):
{bullets_block}

OUTPUT — JSON only, no prose outside:
{{
  "fixes": [
    {{"index": 1, "new": "rewritten bullet text", "strategy": "fill-last-line", "detail_added": "what specific detail you restored from base resume"}},
    {{"index": 2, "new": "rewritten bullet text", "strategy": "fit-one-line", "detail_added": "(none — base resume has no more meaningful detail)"}}
  ]
}}

Strategy must be "fill-last-line" (preferred) or "fit-one-line" (fallback only). Index matches [N] above. detail_added must name the specific item restored or explicitly state none was available.
"""

    try:
        resp = client.messages.create(
            model=_FIX_MODEL,
            max_tokens=_FIX_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("no JSON in response")
        fixes = json.loads(raw[start:end]).get("fixes", [])
    except Exception as e:
        _log.warning("render-feedback fix call failed: %s", e)
        audit.append(
            f"Render-feedback: found {len(bad_pairs)} bad-wrap bullet(s) but auto-fix call failed ({e})."
        )
        return resume_data, audit

    fixed = 0
    for fx in fixes:
        try:
            i = int(fx["index"]) - 1
            new_text = fx["new"].strip()
            strategy = fx.get("strategy", "?")
            detail = (fx.get("detail_added") or "").strip()
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if i < 0 or i >= len(bad_pairs):
            continue
        if not new_text:
            continue
        r, (group, gi, bi, original) = bad_pairs[i]
        resume_data[group][gi]["bullets"][bi] = new_text
        note = (
            f"Render-feedback fix: {group}[{gi}] bullet {bi+1} "
            f"(was {len(original)} chars, {r.n_lines} lines @ {r.fill_ratio:.0%} fill) "
            f"→ {len(new_text)} chars [{strategy}]"
        )
        if detail:
            note += f" — restored: {detail}"
        audit.append(note)
        fixed += 1

    if fixed == 0:
        audit.append(
            f"Render-feedback: detected {len(bad_pairs)} bad-wrap bullet(s) but no valid rewrites returned."
        )
    elif fixed < len(bad_pairs):
        audit.append(
            f"Render-feedback: fixed {fixed}/{len(bad_pairs)} bad-wrap bullet(s) — others kept original."
        )
    return resume_data, audit
