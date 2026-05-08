"""Cover letter generation via Claude Opus 4.7.

Uses an 8-part format, with body-section ordering that flips based on the
resume variant (research-first vs. work-first).
"""
import json
import os
from datetime import date

import anthropic

from .prompts import ANTI_SLOP_RULES, COVER_LETTER_PROMPT
from .utils import build_company_address_line

# Optional local post-processing pass for voice/style calibration.
# If the module isn't present (public clone), fall back to a no-op so the
# rest of the pipeline still produces a usable letter.
try:
    from .humanizer import humanize_cover_letter  # type: ignore
except ImportError:
    def humanize_cover_letter(draft: str) -> str:
        return draft

MODEL = "claude-opus-4-7"
MAX_TOKENS = 2500

# Research-first ordering fits policy/research/academic roles.
# Work-first fits consulting/finance/industry analyst roles.
RESEARCH_FIRST_RESUMES = {"EconPolicy", "ResearchAnalyst"}

_RESEARCH_GUIDANCE = (
    "Showcase one or two pieces of independent or commissioned research from the "
    "resume above. Name the project, the method, and what was produced or found. "
    "Connect this to a specific requirement in the JD."
)
_COURSEWORK_GUIDANCE = (
    "Briefly tie relevant graduate coursework (drawn from the resume) to the "
    "technical demands of the role. Do not list every course. Pick the two or "
    "three that actually matter for this job and say why."
)
_WORK_GUIDANCE = (
    "Highlight 1-2 professional experiences from the resume most relevant to this JD. "
    "Focus on what was done and the outcome — not job duties. Pull concrete metrics "
    "from the resume bullets when they exist."
)


def _ordering(resume_version: str):
    """Return (label_1, guidance_1, label_2, guidance_2, label_3, guidance_3, ordering_label)."""
    if resume_version in RESEARCH_FIRST_RESUMES:
        return (
            "INDEPENDENT RESEARCH", _RESEARCH_GUIDANCE,
            "GRADUATE COURSEWORK", _COURSEWORK_GUIDANCE,
            "WORK EXPERIENCE", _WORK_GUIDANCE,
            "research-first",
        )
    return (
        "WORK EXPERIENCE", _WORK_GUIDANCE,
        "INDEPENDENT RESEARCH", _RESEARCH_GUIDANCE,
        "GRADUATE COURSEWORK", _COURSEWORK_GUIDANCE,
        "work-first",
    )


def _build_job_context(job: dict, jd_text: str) -> str:
    parts = [
        f"Job Title: {job['title']}",
        f"Company: {job['company']}",
        f"Location: {job.get('location', '')}",
    ]
    if jd_text:
        parts.append(f"\nJob Description:\n{jd_text}")
    else:
        parts.append("\n(Job description unavailable — work from title and company only.)")
    return "\n".join(parts)


def generate_cover_letter(job: dict, resume_text: str, resume_version: str, jd_text: str) -> dict:
    """Returns {cover_letter_text, used_passion_statement, body_ordering}.

    Raises on API or parse failure; caller handles.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    l1, g1, l2, g2, l3, g3, ordering_label = _ordering(resume_version)

    # Either "" (no city line) or "\n   <City, ST>" — concatenated directly
    # after the company name in the prompt header so the line vanishes
    # when the scraper produced a junk location like "4 Locations Available".
    company_address_line_full = build_company_address_line(job.get("location") or "")

    prompt = COVER_LETTER_PROMPT.format(
        job_context=_build_job_context(job, jd_text),
        resume_version=resume_version,
        resume_text=resume_text,
        today_date=date.today().strftime("%B %d, %Y"),
        company=job["company"],
        company_address_line_full=company_address_line_full,
        body_section_1_label=l1, body_section_1_guidance=g1,
        body_section_2_label=l2, body_section_2_guidance=g2,
        body_section_3_label=l3, body_section_3_guidance=g3,
        body_ordering_label=ordering_label,
        anti_slop_rules=ANTI_SLOP_RULES,
    )

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError(f"Cover letter response had no JSON block: {raw[:300]}")
    data = json.loads(raw[start:end])
    if "cover_letter_text" not in data:
        raise ValueError("Cover letter JSON missing 'cover_letter_text'")
    data.setdefault("audit_notes", [])
    # Optional voice-calibration pass. No-op if humanize_cover_letter is the
    # stub (module not installed); otherwise runs the local humanizer.
    data["cover_letter_text"] = humanize_cover_letter(data["cover_letter_text"])
    return data
