"""
JobPipeline Daily Automation
  Phase 1 — Run all scrapers
  Phase 2 — Score new unscored jobs against your 4 resumes
  Phase 3 — Auto-delete jobs below match threshold (no prompt)

Run manually:   python daily_run.py
Schedule:       Windows Task Scheduler (see instructions at bottom of file)
Re-run safe:    already-scored jobs are skipped automatically
"""

import os, sys, time, logging
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Windows console (cp1252) chokes on ✓/✗ — force UTF-8 on stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import anthropic
import db
from scrapers.run_all import SCRAPERS
from score_jobs import load_resumes, fetch_description, score_job
from h1b_sponsors import get_h1b_status

# ── Config ────────────────────────────────────────────────────────────────────

THRESHOLD   = 75     # jobs below this % are auto-deleted
SCORE_DELAY = 0.3    # seconds between Claude API calls

# ── Logging (console + daily log file) ───────────────────────────────────────

LOG_DIR  = os.path.join(ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Phase 1: Scrape ───────────────────────────────────────────────────────────

def phase1_scrape():
    log.info("=" * 55)
    log.info("PHASE 1 — Scraping")
    log.info("=" * 55)

    db.init_db()
    total_new = 0
    results   = []

    for ScraperClass in SCRAPERS:
        scraper = ScraperClass()
        try:
            new = scraper.run()
            results.append((scraper.COMPANY, new, None))
            total_new += new
        except Exception as e:
            results.append((scraper.COMPANY, 0, str(e)))
            log.warning(f"  {scraper.COMPANY}: FAILED — {e}")
        time.sleep(1)

    log.info("")
    for company, new, err in results:
        status = f"+{new} new" if err is None else "ERROR"
        log.info(f"  {company:<30} {status}")
    log.info(f"\n  Total added this run: {total_new}")
    return total_new


# ── Phase 2: Score ────────────────────────────────────────────────────────────

def phase2_score():
    log.info("")
    log.info("=" * 55)
    log.info("PHASE 2 — Scoring")
    log.info("=" * 55)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.error("  ANTHROPIC_API_KEY not set — skipping scoring.")
        return 0

    resumes = load_resumes()
    if not resumes:
        log.error("  No resume files found — skipping scoring.")
        return 0

    client  = anthropic.Anthropic(api_key=api_key)
    all_new = db.list_jobs(status="New")
    to_score = [j for j in all_new if j.get("match_score") is None]
    already  = len(all_new) - len(to_score)

    log.info(f"  To score: {len(to_score)}  (skipping {already} already scored)")
    log.info(f"  Threshold: {THRESHOLD}%")
    log.info("")

    scored = failed = 0
    for i, job in enumerate(to_score, 1):
        label  = f"[{i}/{len(to_score)}]"
        title  = f"{job['title'][:38]:<38}"
        result = score_job(client, job, resumes)

        if result:
            db.update_job(
                job["id"],
                match_score=result["score"],
                matched_resume=result["best_resume"],
            )
            if result.get("disqualified"):
                flag = "DQ"
            elif result["score"] >= THRESHOLD:
                flag = "✓"
            else:
                flag = "✗"
            country = result.get("country") or "??"
            log.info(f"  {label} {title} {result['score']:>3}%  [{country:<3}] [{result['best_resume']}]  {flag}")
            scored += 1
        else:
            log.warning(f"  {label} {title} FAILED")
            failed += 1

        time.sleep(SCORE_DELAY)

    log.info(f"\n  Scored: {scored}  |  Failed: {failed}")
    return scored


# ── Phase 4: H1B enrichment ──────────────────────────────────────────────────

def phase4_h1b():
    log.info("")
    log.info("=" * 55)
    log.info("PHASE 4 — H1B Sponsor Tagging")
    log.info("=" * 55)

    all_jobs = db.list_jobs()
    unknown  = [
        j for j in all_jobs
        if j.get("h1b_status") in (None, "Unknown", "")
        and j.get("status") != "Dismissed"
    ]
    tagged   = 0

    for job in unknown:
        status = get_h1b_status(job.get("company", ""))
        if status != "Unknown":
            db.update_job(job["id"], h1b_status=status)
            tagged += 1

    sponsors = sum(1 for j in db.list_jobs() if j.get("h1b_status") == "Known Sponsor")
    log.info(f"  Tagged: {tagged} jobs  |  Total Known Sponsors in pipeline: {sponsors}")


# ── Phase 3: Auto-dismiss below threshold ─────────────────────────────────────
#
# Soft-delete (status='Dismissed') rather than DELETE, so the unique URL
# survives and the same posting won't be re-scraped next run.

def phase3_cleanup():
    log.info("")
    log.info("=" * 55)
    log.info(f"PHASE 3 — Auto-dismissing jobs below {THRESHOLD}%")
    log.info("=" * 55)

    all_new     = db.list_jobs(status="New")
    to_dismiss  = [
        j for j in all_new
        if j.get("match_score") is not None and j["match_score"] < THRESHOLD
    ]

    for j in to_dismiss:
        db.update_job(j["id"], status="Dismissed")

    log.info(f"  Dismissed: {len(to_dismiss)} jobs")
    return len(to_dismiss)


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary():
    log.info("")
    log.info("=" * 55)
    log.info("SUMMARY")
    log.info("=" * 55)

    all_jobs  = db.list_jobs()
    active    = [j for j in all_jobs if j.get("status") != "Dismissed"]
    stats     = db.get_stats()
    by_status = stats.get("by_status", {})

    log.info(f"  Total jobs in pipeline: {len(active)}  (dismissed: {len(all_jobs) - len(active)})")
    for status in ["New", "Interested", "Applied", "Interview", "Offer", "Rejected"]:
        n = by_status.get(status, 0)
        if n:
            log.info(f"    {status}: {n}")

    new_jobs = db.list_jobs(status="New")
    scored   = [j for j in new_jobs if j.get("match_score") is not None]
    if scored:
        avg = round(sum(j["match_score"] for j in scored) / len(scored), 1)
        log.info(f"\n  Avg match score (New): {avg}%")

        by_resume = {}
        for j in scored:
            rv = j.get("matched_resume") or "Unassigned"
            by_resume[rv] = by_resume.get(rv, 0) + 1
        for rv, count in sorted(by_resume.items(), key=lambda x: -x[1]):
            log.info(f"    {rv}: {count} jobs")

    log.info(f"\n  Full log: {log_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    start = datetime.now()
    log.info(f"\nJobPipeline Daily Run — {start.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        phase1_scrape()
        phase2_score()
        phase3_cleanup()
        phase4_h1b()
        print_summary()
    except Exception as e:
        log.exception(f"Fatal error in daily run: {e}")
        sys.exit(1)

    elapsed = round((datetime.now() - start).total_seconds())
    log.info(f"\nCompleted in {elapsed}s\n")


if __name__ == "__main__":
    main()


# ── Windows Task Scheduler Setup ──────────────────────────────────────────────
#
# Replace <path-to-JobPipeline> below with your actual project path.
#
# 1. Open Task Scheduler (search "Task Scheduler" in Start menu)
# 2. Click "Create Basic Task" → name it "JobPipeline Daily"
# 3. Trigger: Daily, set your preferred time (e.g. 8:00 AM)
# 4. Action: "Start a program"
#    Program:   <path-to-JobPipeline>\venv\Scripts\python.exe
#    Arguments: <path-to-JobPipeline>\daily_run.py
#    Start in:  <path-to-JobPipeline>
# 5. Finish — logs will appear in JobPipeline\logs\YYYY-MM-DD.log
