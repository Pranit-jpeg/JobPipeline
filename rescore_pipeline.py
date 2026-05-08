"""Re-score the back catalog with the fixed JD fetcher.

Targets jobs that were scored while the scorer was blind (static-only fetch
returning empty shells from JS-rendered ATS pages). Re-fetches each JD via
the generator's static-plus-Playwright fetcher and re-runs Haiku.

Modes:
  --dry-run    print intended changes, don't write
  --new        re-score status=New only
  --dismissed  re-score status=Dismissed only
  --all        re-score both (default)
  --max N      cap to N jobs (useful for testing)

Always SKIPS Applied + Interested — those are user decisions, not pipeline
auto-judgments. If you want to re-evaluate a posting you already applied
to, do it manually.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 stdout so the ✓/✗ markers don't crash on cp1252.
# Also force line-buffering — when this script runs in the background with
# stdout redirected to a file, Python's default block buffering hides progress
# until the buffer fills (~8KB) or the script exits. Line-buffering means
# every print flushes immediately, so background tail-f works in real time.
for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from dotenv import load_dotenv
load_dotenv()

import anthropic

import db
from score_jobs import load_resumes, score_job, THRESHOLD


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print intended changes; don't write to the DB")
    ap.add_argument("--new", action="store_true",
                    help="Re-score status=New only (default: both)")
    ap.add_argument("--dismissed", action="store_true",
                    help="Re-score status=Dismissed only (default: both)")
    ap.add_argument("--max", type=int, default=0,
                    help="Cap to N jobs (0 = no cap)")
    ap.add_argument("--promote-rescued", action="store_true",
                    help="After scoring, flip any Dismissed job whose new score "
                         "≥ threshold and whose OLD score was < threshold back "
                         "to status='New'. Only touches auto-rescued jobs — "
                         "manually-dismissed high-score jobs are left alone.")
    ap.add_argument("--min-score", type=int, default=0,
                    help="Only re-score jobs whose CURRENT match_score >= N. "
                         "Useful for A/B-testing models on borderline jobs only.")
    ap.add_argument("--model", default=None,
                    choices=["haiku", "sonnet", "opus"],
                    help="Override the scoring model. Default uses score_jobs.MODEL "
                         "(Haiku). Use 'sonnet' to A/B-test against Haiku.")
    args = ap.parse_args()

    model_id = {
        "haiku":  "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-6",
        "opus":   "claude-opus-4-7",
    }.get(args.model)

    db.init_db()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ANTHROPIC_API_KEY not set"); sys.exit(1)

    statuses = []
    if args.new:           statuses = ["New"]
    elif args.dismissed:   statuses = ["Dismissed"]
    else:                  statuses = ["New", "Dismissed"]

    # Pull every candidate job up front so we can stop on --max cleanly.
    candidates = []
    for st in statuses:
        candidates.extend(db.list_jobs(status=st))
    if args.min_score:
        candidates = [j for j in candidates
                      if (j.get("match_score") or 0) >= args.min_score]
    if args.max:
        candidates = candidates[: args.max]

    model_label = (args.model or "default-haiku")
    min_label   = f", min_score>={args.min_score}" if args.min_score else ""
    print(f"Re-scoring {len(candidates)} jobs ({', '.join(statuses)}{min_label})  "
          f"model={model_label}  "
          f"{'[DRY RUN]' if args.dry_run else '[LIVE]'}")
    print()

    client = anthropic.Anthropic(api_key=api_key)
    resumes = load_resumes()

    deltas = []   # tuples of (job, old_score, new_score, new_resume)
    failures = 0

    for i, job in enumerate(candidates, 1):
        old_score   = job.get("match_score")
        old_resume  = job.get("matched_resume") or "—"
        title  = (job.get("title") or "")[:42]
        source = job.get("source") or "?"

        try:
            result = score_job(client, job, resumes, model=model_id)
        except Exception as e:
            print(f"  [{i}/{len(candidates)}] ERROR  {title:<42}  {e}")
            failures += 1
            continue

        if not result:
            print(f"  [{i}/{len(candidates)}] FAIL   {title:<42}  (scorer returned None)")
            failures += 1
            continue

        new_score  = result["score"]
        new_resume = result.get("best_resume") or "—"

        delta = (new_score or 0) - (old_score or 0)
        sign = "+" if delta >= 0 else ""
        flag = " ↑" if delta >= 10 else (" ↓" if delta <= -10 else "  ")
        print(f"  [{i}/{len(candidates)}]{flag} {old_score!s:>3} -> {new_score:>3} "
              f"({sign}{delta:>3})  [{source[:14]:<14}] {title}")

        if not args.dry_run and (delta != 0 or new_resume != old_resume):
            db.update_job(job["id"],
                          match_score=new_score,
                          matched_resume=new_resume)
        deltas.append((job, old_score, new_score, new_resume))
        time.sleep(0.3)

    # ── Summary ────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print(f"SUMMARY  ({'DRY RUN — no DB writes' if args.dry_run else 'DB updated'})")
    print("=" * 70)

    if failures:
        print(f"Failures: {failures}")

    # Categorize the deltas
    rescued    = []  # was Dismissed (below 75) but new score >= 75
    overscored = []  # was New (>=75) but new score < 75
    big_jumps  = []  # |delta| >= 15

    for job, old, new, _ in deltas:
        if old is None:
            continue
        old_below = old < THRESHOLD
        new_above = new >= THRESHOLD
        # Only auto-dismissed jobs are eligible for rescue. User-dismissed jobs
        # (auto_dismissed=0) carry context the scorer can't see — pay range,
        # application workload, perceived fit. They stay dismissed regardless
        # of how high the new score is.
        if (old_below and new_above
                and job.get("status") == "Dismissed"
                and job.get("auto_dismissed")):
            rescued.append((job, old, new))
        if (not old_below) and (not new_above) and job.get("status") == "New":
            overscored.append((job, old, new))
        if abs(new - old) >= 15:
            big_jumps.append((job, old, new))

    print(f"\nRescued from Dismissed (old < {THRESHOLD}, new ≥ {THRESHOLD}): {len(rescued)}")
    for j, o, n in sorted(rescued, key=lambda x: -(x[2] - x[1])):
        print(f"  {o:>3} -> {n:>3}  [{j.get('source','?'):<14}] {j['title'][:60]}")
        print(f"             {j.get('url')}")

    print(f"\nOver-scored New jobs (old ≥ {THRESHOLD}, new < {THRESHOLD}): {len(overscored)}")
    for j, o, n in sorted(overscored, key=lambda x: x[2] - x[1]):
        print(f"  {o:>3} -> {n:>3}  [{j.get('source','?'):<14}] {j['title'][:60]}")

    print(f"\nLarge swings (|Δ| ≥ 15): {len(big_jumps)} (top 10 by magnitude)")
    for j, o, n in sorted(big_jumps, key=lambda x: -abs(x[2] - x[1]))[:10]:
        sign = "+" if n - o > 0 else ""
        print(f"  {o:>3} -> {n:>3}  ({sign}{n-o:>3})  [{j.get('source','?'):<14}] {j['title'][:55]}")

    # Optional auto-promote — flip rescued Dismissed jobs back to New so
    # they reappear in the normal review flow. The rescued list is already
    # filtered to auto_dismissed=1 only, so user-dismissed jobs are never
    # touched here regardless of how the score moved.
    if args.promote_rescued and not args.dry_run and rescued:
        print(f"\nPromoting {len(rescued)} rescued job(s) back to New status...")
        for j, _, _ in rescued:
            db.update_job(j["id"], status="New")
            print(f"  id={j['id']:<5}  Dismissed -> New  [{j.get('source','?')}] {j['title'][:55]}")
    elif args.promote_rescued and args.dry_run:
        print(f"\n(--dry-run: would promote {len(rescued)} rescued job(s) but not writing)")


if __name__ == "__main__":
    main()
