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

# ── Config ────────────────────────────────────────────────────────────────────

THRESHOLD   = 75
MODEL       = "claude-haiku-4-5-20251001"
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
    """Fetch and clean job page text. Returns empty string on failure."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
        return "\n".join(lines)[:4000]
    except Exception:
        return ""


def score_job(client, job, resumes):
    """
    Ask Claude which resume fits best and return a 0-100 match score.
    Returns dict {score, best_resume, reasoning} or None on failure.
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

    prompt = f"""You are a career advisor helping a recent economics graduate (MS Economics, May 2026, 19 months experience, F-1/OPT visa) find the best-fit entry-level jobs.

Evaluate how well each resume matches the job below. Consider: skill overlap, relevant experience, industry fit, and keyword alignment.

JOB:
{job_context}

RESUMES:
{resume_block}

Respond with ONLY valid JSON — no extra text:
{{
  "best_resume": "<one of: EconPolicy, FinanceConsulting, DataAnalyst, ResearchAnalyst>",
  "score": <integer 0-100 representing match quality of the best resume>,
  "reasoning": "<one sentence>"
}}"""

    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                return {
                    "score":       max(0, min(100, int(data["score"]))),
                    "best_resume": data.get("best_resume", ""),
                    "reasoning":   data.get("reasoning", ""),
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
