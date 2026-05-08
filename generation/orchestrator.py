"""Top-level entry point: takes a job dict, returns paths to the two PDFs.

Runs the LLM calls in parallel threads, renders to PDF, then runs a
render-feedback wrap-fix loop: parses the rendered PDF, identifies bullets
that wrapped with mostly-empty last lines, asks the model to rewrite, and
re-renders.
"""
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import anthropic

from profile import PROFILE

from .cover_letter import generate_cover_letter
from .docx_writer import (
    convert_to_pdf,
    pdf_page_count,
    write_cover_letter_docx,
    write_resume_docx,
)
from .resume_tailor import tailor_resume
from .utils import GENERATED_DIR, fetch_jd, load_resume, slugify
from .wrap_check import remediate_wraps_with_render_feedback

MAX_TIGHTNESS = 8
# Number of render-check-fix cycles allowed. The first call fixes any bad
# bullets in the initial render; each subsequent iteration catches bullets
# whose rewrites still wrap badly. 3 = first attempt + 2 retries.
MAX_WRAP_ITERATIONS = 3
log = logging.getLogger(__name__)


def _robust_page_count(pdf_path: str) -> int:
    """Read the page count twice with a short delay between reads.

    On Windows, docx2pdf's subprocess can return before Word has finished
    flushing the PDF. Reading too soon can return a stale/partial count.
    Taking the max of two reads separated by a short sleep defeats the race.
    """
    time.sleep(0.3)
    pages1 = pdf_page_count(pdf_path)
    time.sleep(0.3)
    pages2 = pdf_page_count(pdf_path)
    return max(pages1, pages2)


def _render_one_page(render_docx, docx_path: str, pdf_path: str) -> int:
    """Render at increasing tightness until the PDF fits on one page or we hit max."""
    for tightness in range(MAX_TIGHTNESS + 1):
        render_docx(tightness)
        convert_to_pdf(docx_path, pdf_path)
        pages = _robust_page_count(pdf_path)
        log.info("render tightness=%d -> %d pages (%s)", tightness, pages, os.path.basename(pdf_path))
        if pages <= 1:
            return tightness
    log.warning("still >1 page at max tightness (%d): %s", MAX_TIGHTNESS, os.path.basename(pdf_path))
    return MAX_TIGHTNESS


# Tool / language / software names a cover letter sometimes claims that the
# resume needs to back up. The list is intentionally conservative — only
# specific products and languages, not generic skills like "regression" or
# "modeling" (which are method names, not tools, and routinely paraphrase).
_TOOL_TOKENS = [
    "SQL", "Python", "R", "Stata", "SAS", "SPSS", "MATLAB",
    "Tableau", "Power BI", "PowerBI", "Excel", "PowerPoint",
    "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch", "Keras",
    "Spark", "Hadoop", "Hive", "Snowflake", "BigQuery", "Redshift",
    "AWS", "GCP", "Azure",
    "Git", "GitHub", "Docker", "Kubernetes", "Jupyter",
    "BeautifulSoup", "Selenium", "Zotero", "QGIS", "ArcGIS",
    "Looker", "dbt", "Airflow",
]


def _resume_corpus(resume_data: dict) -> str:
    """Flatten everything in the tailored resume to a single searchable string."""
    parts: list[str] = [
        resume_data.get("professional_summary") or "",
    ]
    skills = resume_data.get("skills") or {}
    if isinstance(skills, dict):
        parts.extend(str(v) for v in skills.values())
    for role in resume_data.get("work_experience") or []:
        parts.extend(role.get("bullets") or [])
    for proj in resume_data.get("academic_projects") or []:
        parts.extend(proj.get("bullets") or [])
        parts.append(proj.get("name") or "")
    return "\n".join(parts)


def _check_tool_fidelity(cover_letter_text: str, resume_data: dict) -> list[str]:
    """Flag any tool name in the letter that the tailored resume cannot back up.

    Returns a list of human-readable audit notes (one per offending tool).
    The post-render audit is a backstop — the prompt-level rule should
    prevent these from being produced in the first place.
    """
    if not cover_letter_text:
        return []
    haystack = _resume_corpus(resume_data).lower()
    notes: list[str] = []
    for token in _TOOL_TOKENS:
        # Word-boundary regex; case-insensitive. \b alone won't handle "Power BI"
        # (the space breaks it), so we anchor on non-word boundaries instead.
        pat = re.compile(r"(?<!\w)" + re.escape(token) + r"(?!\w)", re.IGNORECASE)
        if pat.search(cover_letter_text) and token.lower() not in haystack:
            notes.append(
                f"Tool fidelity: cover letter mentions '{token}' but the "
                f"tailored resume does not list it. Verify the claim before sending."
            )
    return notes


def _pick_resume_version(job: dict) -> str:
    return job.get("resume_version") or job.get("matched_resume") or "ResearchAnalyst"


def _output_dir(job: dict) -> str:
    folder = f"{slugify(job['company'])}_{slugify(job['title'])}_{date.today().strftime('%Y%m%d')}"
    path = os.path.join(GENERATED_DIR, folder)
    os.makedirs(path, exist_ok=True)
    return path


def generate_application(job: dict) -> dict:
    """Returns dict with paths + metadata. Raises on hard failure."""
    resume_version = _pick_resume_version(job)
    resume_text = load_resume(resume_version)
    if not resume_text:
        raise FileNotFoundError(f"Base resume '{resume_version}' not found in resumes/")

    jd_text = fetch_jd(job.get("url", ""))
    jd_chars = len(jd_text)
    log.info("fetched JD: %d chars from %s", jd_chars, job.get("url", ""))
    out_dir = _output_dir(job)

    # Parallel LLM calls
    with ThreadPoolExecutor(max_workers=2) as ex:
        resume_future = ex.submit(tailor_resume, job, resume_text, resume_version, jd_text)
        cover_future = ex.submit(generate_cover_letter, job, resume_text, resume_version, jd_text)
        resume_data = resume_future.result()
        cover_data = cover_future.result()

    # Post-generation backstop: catch tool/skill claims in the cover letter
    # that the tailored resume cannot back up. Prompt-level rules should
    # prevent these, but we surface anything that slips through to the user.
    fidelity_notes = _check_tool_fidelity(
        cover_data.get("cover_letter_text") or "",
        resume_data,
    )
    if fidelity_notes:
        cover_data.setdefault("audit_notes", []).extend(fidelity_notes)
        for n in fidelity_notes:
            log.warning(n)

    company_slug = slugify(job["company"], max_len=24)
    role_slug = slugify(job.get("title", ""), max_len=32)
    name_slug = PROFILE["name_slug"]
    suffix = f"{company_slug}_{role_slug}" if role_slug else company_slug
    resume_docx = os.path.join(out_dir, f"{name_slug}_Resume_{suffix}.docx")
    cover_docx = os.path.join(out_dir, f"{name_slug}_CoverLetter_{suffix}.docx")
    resume_pdf = resume_docx.replace(".docx", ".pdf")
    cover_pdf = cover_docx.replace(".docx", ".pdf")

    pdf_error = None
    resume_tightness_used = 0
    cover_tightness_used = 0
    render_feedback_notes: list[str] = []
    try:
        resume_tightness_used = _render_one_page(
            lambda t: write_resume_docx(resume_data, resume_docx, tightness=t),
            resume_docx, resume_pdf,
        )

        # Render-feedback wrap fix: parse rendered PDF, find bullets that
        # wrapped with empty last lines, ask the model to rewrite, re-render.
        # Grounded in the actual rendered output. We iterate because Opus's
        # rewrites occasionally still wrap badly (it can't perfectly predict
        # wraps); each iteration catches what the previous one missed.
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key and resume_pdf and os.path.exists(resume_pdf):
            client = anthropic.Anthropic(api_key=api_key)
            for iteration in range(MAX_WRAP_ITERATIONS):
                resume_data, iter_notes = remediate_wraps_with_render_feedback(
                    resume_data, resume_pdf, resume_text, client,
                )
                if iteration > 0:
                    # Tag iteration notes so the audit log shows which pass found what.
                    iter_notes = [f"[iter {iteration+1}] {n}" for n in iter_notes]
                render_feedback_notes.extend(iter_notes)
                fixes_made = any(n for n in iter_notes if "Render-feedback fix:" in n)
                if not fixes_made:
                    # Either everything was already clean, or the fix call
                    # returned no valid rewrites — either way, stop.
                    break
                # Re-render with the fixed bullets and loop to re-check.
                resume_tightness_used = _render_one_page(
                    lambda t: write_resume_docx(resume_data, resume_docx, tightness=t),
                    resume_docx, resume_pdf,
                )

        cover_tightness_used = _render_one_page(
            lambda t: write_cover_letter_docx(cover_data["cover_letter_text"], cover_docx, tightness=t),
            cover_docx, cover_pdf,
        )
    except Exception as e:
        pdf_error = str(e)
        resume_pdf = None
        cover_pdf = None

    return {
        "resume_version": resume_version,
        "body_ordering": cover_data.get("body_ordering"),
        "used_passion_statement": cover_data.get("used_passion_statement"),
        "changes_summary": resume_data.get("changes_summary", []),
        "ats_keywords": resume_data.get("ats_keywords", []),
        "resume_audit_notes": resume_data.get("audit_notes", []) + render_feedback_notes,
        "cover_letter_audit_notes": cover_data.get("audit_notes", []),
        "jd_chars": jd_chars,
        "resume_tightness": resume_tightness_used,
        "cover_letter_tightness": cover_tightness_used,
        "output_dir": out_dir,
        "resume_docx": resume_docx,
        "resume_pdf": resume_pdf,
        "cover_letter_docx": cover_docx,
        "cover_letter_pdf": cover_pdf,
        "cover_letter_preview": cover_data["cover_letter_text"],
        "pdf_error": pdf_error,
    }
