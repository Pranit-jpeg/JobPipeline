"""
One-off cleanup: delete all New-status jobs from scrapers we've dropped
(government + academic). Preserves any records with status != New
(e.g. an Applied nyc_gov posting) so your application history stays intact.

Run once:  python cleanup_dropped_sources.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db

DROPPED_SOURCES = [
    # Government (visa dead-ends)
    "usajobs", "treasury", "usda_ers", "mass_gov", "nyc_gov",
    # Academic (not corporate per career focus)
    "predoc", "harvard", "mit", "stanford", "uchicago", "bfi", "jpab",
    # Blocks headless browsers (kept as files, not imported)
    "goldman", "microsoft",
]


def main():
    db.init_db()

    all_new = db.list_jobs(status="New")
    targets = [j for j in all_new if j.get("source") in DROPPED_SOURCES]

    # Breakdown before deleting
    by_source = {}
    for j in targets:
        by_source[j["source"]] = by_source.get(j["source"], 0) + 1

    print(f"Found {len(targets)} New jobs to delete from dropped sources:")
    for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {src:<12} {n}")

    # Also tell the user what's being preserved
    all_jobs = db.list_jobs()
    preserved = [j for j in all_jobs
                 if j.get("source") in DROPPED_SOURCES and j.get("status") != "New"]
    if preserved:
        print(f"\nPreserving {len(preserved)} non-New record(s):")
        for j in preserved:
            print(f"  [{j['status']}] {j['title']} @ {j['company']} ({j['source']})")

    if not targets:
        print("\nNothing to delete.")
        return

    confirm = input(f"\nDelete these {len(targets)} jobs? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    deleted = 0
    for j in targets:
        try:
            db.delete_job(j["id"])
            deleted += 1
        except Exception as e:
            print(f"  Failed on id={j['id']}: {e}")

    print(f"\nDeleted {deleted}/{len(targets)} jobs.")

    # Final state
    stats = db.get_stats()
    print("\nPipeline after cleanup:")
    for status, n in stats["by_status"].items():
        print(f"  {status:<12} {n}")


if __name__ == "__main__":
    main()
