"""Resume tailoring via Claude Sonnet 4.6.

Returns a structured resume dict ready for the docx writer. Prompt constrains
the model to rephrasing + reordering existing content; no fabrication.
"""
import json
import os

import anthropic

from .prompts import RESUME_TAILOR_PROMPT

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4000


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


def tailor_resume(job: dict, resume_text: str, resume_version: str, jd_text: str) -> dict:
    """Returns the structured-resume dict described in the prompt."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    prompt = RESUME_TAILOR_PROMPT.format(
        job_context=_build_job_context(job, jd_text),
        resume_version=resume_version,
        resume_text=resume_text,
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
        raise ValueError(f"Resume tailor response had no JSON block: {raw[:300]}")
    data = json.loads(raw[start:end])

    required = {"name", "contact_line", "professional_summary",
                "work_experience", "education", "skills"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Tailored resume JSON missing fields: {missing}")
    return data
