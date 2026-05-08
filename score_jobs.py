"""
Score all 'New' jobs against your 4 resumes using Claude Haiku.
Jobs scoring below THRESHOLD are deleted from the pipeline.

Run:  python score_jobs.py
Re-run safe: already-scored jobs are skipped.
"""

import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import requests
from bs4 import BeautifulSoup
import anthropic
import db
from profile import PROFILE
# Single source of truth for JD fetching. The generator's fetch_jd does
# static-first with a Playwright fallback for JS-rendered pages (Workday,
# Meta, Cornerstone, etc.). Without this, the scorer was getting empty
# shells from every JS-rendered ATS and grading on the title alone.
from generation.utils import fetch_jd as _fetch_jd_with_fallback

# ── Config ────────────────────────────────────────────────────────────────────

THRESHOLD   = 70
MODEL       = "claude-sonnet-4-6"
RESUMES_DIR = os.path.join(os.path.dirname(__file__), "resumes")
DELAY       = 0.3   # seconds between API calls to respect rate limits

RESUME_FILES = {
    "EconPolicy":        "econ_policy.txt",
    "FinanceConsulting": "finance_consulting.txt",
    "DataAnalyst":       "data_analyst.txt",
    "ResearchAnalyst":   "research_analyst.txt",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_resumes():
    resumes = {}
    for key, filename in RESUME_FILES.items():
        path = os.path.join(RESUMES_DIR, filename)
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found — skipping this resume.")
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
        resumes[key] = text[:3000]  # cap to control token cost
    return resumes


def fetch_description(url):
    """Delegates to the generator's static+Playwright fetcher.

    Kept as a thin wrapper so existing callers (daily_run.py imports this
    name) keep working without churn. The 4000-char cap matches the prior
    behavior so prompt token costs don't change.
    """
    return (_fetch_jd_with_fallback(url) or "")[:4000]


def score_job(client, job, resumes, model=None):
    """
    Ask Claude which resume fits best and return a 0-100 match score.
    Returns dict {score, best_resume, reasoning} or None on failure.

    `model` overrides the module-level MODEL default — used by the rescore
    A/B-test path to compare Haiku vs Sonnet on the same job set.
    """
    description = fetch_description(job["url"])

    job_context = (
        f"Job Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
    )
    if description:
        job_context += f"\nJob Description:\n{description}"
    else:
        job_context += "\n(Full description unavailable — scoring on title and company only.)"

    resume_block = "\n\n---\n\n".join(
        f"[{key}]\n{text}" for key, text in resumes.items()
    )

    scoring = PROFILE["scoring"]
    prompt = f"""You are a career advisor helping a recent graduate find the best-fit entry-level jobs.

CANDIDATE: {scoring["candidate_summary"]}

{scoring["location_preferences"]}

{scoring["hard_disqualifiers"]}

Evaluate resume fit (skill overlap, relevant experience, industry fit, keywords), apply the location penalty if applicable, then return final score.

JOB:
{job_context}

RESUMES:
{resume_block}

Respond with ONLY valid JSON — no extra text:
{{
  "best_resume": "<one of: {", ".join(RESUME_FILES.keys())}>",
  "country": "<one of: {scoring["country_codes"]}>",
  "score": <integer 0-100, already reflecting the secondary-country penalty if applicable>,
  "disqualified": <true or false>,
  "reasoning": "<one sentence; if disqualified, state which rule applied>"
}}"""

    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model or MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                score = max(0, min(100, int(data["score"])))
                disqualified = bool(data.get("disqualified", False))
                if disqualified:
                    score = min(score, 20)
                return {
                    "score":        score,
                    "best_resume":  data.get("best_resume", ""),
                    "country":      data.get("country", ""),
                    "disqualified": disqualified,
                    "reasoning":    data.get("reasoning", ""),
                }
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
            else:
                print(f"    Scoring error: {e}")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    db.init_db()
    resumes = load_resumes()
    if not resumes:
        print("ERROR: No resume files found in resumes/")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Only score New jobs that haven't been scored yet
    all_new   = db.list_jobs(status="New")
    to_score  = [j for j in all_new if j.get("match_score") is None]
    already   = len(all_new) - len(to_score)

    print(f"\nJobs to score: {len(to_score)}  (skipping {already} already scored)")
    print(f"Match threshold: {THRESHOLD}%  |  Model: {MODEL}\n")

    if not to_score:
        print("Nothing new to score.")
    else:
        for i, job in enumerate(to_score, 1):
            label = f"[{i}/{len(to_score)}]"
            print(f"{label} {job['title']} @ {job['company']} ... ", end="", flush=True)

            result = score_job(client, job, resumes)
            if result:
                db.update_job(
                    job["id"],
                    match_score=result["score"],
                    matched_resume=result["best_resume"],
                )
                flag = "✓" if result["score"] >= THRESHOLD else "✗"
                print(f"{result['score']}%  [{result['best_resume']}]  {flag}")
            else:
                print("FAILED (skipped)")

            time.sleep(DELAY)

    # ── Phase 2: delete below threshold ──────────────────────────────────────
    all_new_scored = db.list_jobs(status="New")
    to_delete = [
        j for j in all_new_scored
        if j.get("match_score") is not None and j["match_score"] < THRESHOLD
    ]

    print(f"\n{'='*50}")
    print(f"Scored jobs below {THRESHOLD}%: {len(to_delete)}")

    if to_delete:
        confirm = input(f"Delete these {len(to_delete)} low-match jobs? [y/N] ").strip().lower()
        if confirm == "y":
            for j in to_delete:
                db.delete_job(j["id"])
            print(f"Deleted {len(to_delete)} jobs.")

    remaining = db.list_jobs(status="New")
    scored    = [j for j in remaining if j.get("match_score") is not None]
    avg_score = round(sum(j["match_score"] for j in scored) / len(scored), 1) if scored else 0

    print(f"\nNew jobs remaining: {len(remaining)}")
    print(f"Average match score: {avg_score}%")

    by_resume = {}
    for j in scored:
        rv = j.get("matched_resume") or "Unassigned"
        by_resume[rv] = by_resume.get(rv, 0) + 1
    for rv, count in sorted(by_resume.items(), key=lambda x: -x[1]):
        print(f"  {rv}: {count} jobs")


if __name__ == "__main__":
    main()
