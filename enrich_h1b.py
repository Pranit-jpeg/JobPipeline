"""
Backfill H1B sponsor status for all existing jobs in the database.

For each job currently marked "Unknown", this script:
  1. Checks the company name against the known-sponsor list
  2. Optionally fetches the job description to detect explicit phrases
     (set FETCH_DESCRIPTIONS=True below — slower but more accurate)

Run once:  python enrich_h1b.py
Safe to re-run: only updates jobs still marked "Unknown"
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup

import db
from h1b_sponsors import get_h1b_status

# ── Config ────────────────────────────────────────────────────────────────────

FETCH_DESCRIPTIONS = False   # Set True to also scan job pages (much slower)
FETCH_DELAY        = 0.5     # seconds between fetches if enabled
FETCH_TIMEOUT      = 10

# ── Description fetcher ───────────────────────────────────────────────────────

def fetch_description(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
        return "\n".join(lines)[:6000]
    except Exception:
        return ""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    all_jobs = db.list_jobs()

    unknown = [j for j in all_jobs if j.get("h1b_status") in (None, "Unknown", "")]
    known   = len(all_jobs) - len(unknown)

    print(f"\nTotal jobs: {len(all_jobs)}")
    print(f"Already tagged: {known}")
    print(f"To process: {len(unknown)}")
    print(f"Description fetching: {'ON' if FETCH_DESCRIPTIONS else 'OFF'}\n")

    counts = {"Known Sponsor": 0, "No Sponsorship": 0, "Unknown": 0}

    for i, job in enumerate(unknown, 1):
        company = job.get("company", "")
        desc    = ""

        if FETCH_DESCRIPTIONS:
            desc = fetch_description(job.get("url", ""))
            time.sleep(FETCH_DELAY)

        status = get_h1b_status(company, desc)
        db.update_job(job["id"], h1b_status=status)
        counts[status] += 1

        if status != "Unknown":
            print(f"  [{i}/{len(unknown)}] {company:<35} → {status}")

    print(f"\nDone.")
    print(f"  Known Sponsor:  {counts['Known Sponsor']}")
    print(f"  No Sponsorship: {counts['No Sponsorship']}")
    print(f"  Unknown:        {counts['Unknown']}")

    # Show all Known Sponsors found
    sponsors = [j for j in db.list_jobs() if j.get("h1b_status") == "Known Sponsor"]
    if sponsors:
        print(f"\nKnown Sponsor jobs in pipeline: {len(sponsors)}")
        companies = sorted({j["company"] for j in sponsors})
        for c in companies:
            count = sum(1 for j in sponsors if j["company"] == c)
            print(f"  {c}: {count} job(s)")


if __name__ == "__main__":
    main()
