import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8", errors="replace")

import db
db.init_db()

dismissed = [j for j in db.list_jobs() if j.get("status") == "Dismissed"]

# Bucket histogram
buckets = {"0":0,"1-19":0,"20-39":0,"40-59":0,"60-69":0,"70-74":0,"75+":0}
for j in dismissed:
    s = j.get("match_score") or 0
    if s == 0:      buckets["0"] += 1
    elif s < 20:    buckets["1-19"] += 1
    elif s < 40:    buckets["20-39"] += 1
    elif s < 60:    buckets["40-59"] += 1
    elif s < 70:    buckets["60-69"] += 1
    elif s < 75:    buckets["70-74"] += 1
    else:           buckets["75+"] += 1

print(f"Total Dismissed: {len(dismissed)}")
print("Score distribution after rescore:")
for k, v in buckets.items():
    bar = "#" * v
    print(f"  {k:<6}: {v:>3}  {bar}")

print()
print("=" * 70)
print("Dismissed jobs scoring 65-74 (close to threshold) — sorted by score desc:")
print("=" * 70)
near = sorted(
    [j for j in dismissed if 65 <= (j.get("match_score") or 0) < 75],
    key=lambda x: -(x.get("match_score") or 0),
)
for j in near[:30]:
    print(f"  {j.get('match_score'):>3}  [{j.get('source'):<14}] {j['title'][:62]}")
    print(f"        {(j.get('url') or '')[:95]}")
