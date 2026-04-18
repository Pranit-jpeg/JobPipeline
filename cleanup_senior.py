"""
One-time cleanup: deletes 'New' status jobs whose titles fail the entry-level filter.
Only touches New — any job you've already moved to Interested/Applied/etc. is safe.

Run: python cleanup_senior.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from scrapers.base import is_entry_level

db.init_db()

all_new = db.list_jobs(status="New")
print(f"New jobs before cleanup: {len(all_new)}")

to_delete = [j for j in all_new if not is_entry_level(j["title"])]
print(f"Senior/mid-level titles to remove: {len(to_delete)}")

if not to_delete:
    print("Nothing to delete.")
    sys.exit()

# Show a sample so you can sanity-check before confirming
print("\nSample of titles being removed (first 20):")
for j in to_delete[:20]:
    print(f"  [{j['id']:>5}] {j['title']} @ {j['company']}")
if len(to_delete) > 20:
    print(f"  ... and {len(to_delete) - 20} more")

confirm = input(f"\nDelete all {len(to_delete)} jobs? [y/N] ").strip().lower()
if confirm != "y":
    print("Cancelled.")
    sys.exit()

for j in to_delete:
    db.delete_job(j["id"])

remaining = db.list_jobs(status="New")
print(f"\nDone. New jobs remaining: {len(remaining)}")
