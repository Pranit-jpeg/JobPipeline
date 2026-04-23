"""Top-level entry point: takes a job dict, returns paths to the two PDFs.

Runs the LLM calls in parallel threads, then renders + converts to PDF.
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

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

MAX_TIGHTNESS = 4
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
    out_dir = _output_dir(job)

    # Parallel LLM calls
    with ThreadPoolExecutor(max_workers=2) as ex:
        resume_future = ex.submit(tailor_resume, job, resume_text, resume_version, jd_text)
        cover_future = ex.submit(generate_cover_letter, job, resume_text, resume_version, jd_text)
        resume_data = resume_future.result()
        cover_data = cover_future.result()

    company_slug = slugify(job["company"])
    name_slug = PROFILE["name_slug"]
    resume_docx = os.path.join(out_dir, f"{name_slug}_Resume_{company_slug}.docx")
    cover_docx = os.path.join(out_dir, f"{name_slug}_CoverLetter_{company_slug}.docx")
    resume_pdf = resume_docx.replace(".docx", ".pdf")
    cover_pdf = cover_docx.replace(".docx", ".pdf")

    pdf_error = None
    resume_tightness_used = 0
    cover_tightness_used = 0
    try:
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
