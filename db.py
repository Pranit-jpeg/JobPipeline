import sqlite3
from datetime import date
from config import DB_PATH, STATUSES, RESUME_VERSIONS


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                title          TEXT NOT NULL,
                company        TEXT NOT NULL,
                location       TEXT NOT NULL,
                salary         TEXT,
                url            TEXT UNIQUE NOT NULL,
                date_scraped   TEXT NOT NULL,
                date_posted    TEXT,
                date_applied   TEXT,
                resume_version TEXT,
                notes          TEXT DEFAULT '',
                h1b_status     TEXT DEFAULT 'Unknown',
                source         TEXT NOT NULL,
                status         TEXT DEFAULT 'New'
            )
        """)
        # Add columns to existing databases that predate them
        for col_def in [
            "ALTER TABLE jobs ADD COLUMN date_posted TEXT",
            "ALTER TABLE jobs ADD COLUMN match_score INTEGER",
            "ALTER TABLE jobs ADD COLUMN matched_resume TEXT",
        ]:
            try:
                conn.execute(col_def)
            except Exception:
                pass
    print("Database initialized.")


def add_job(title, company, location, url, source, salary=None, date_posted=None, h1b_status="Unknown"):
    """Add a job. Returns True if added, False if duplicate (same URL)."""
    try:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO jobs
                   (title, company, location, salary, url, date_scraped, date_posted, source, status, h1b_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'New', ?)""",
                (title, company, location, salary, url,
                 date.today().isoformat(), date_posted, source, h1b_status),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_job(job_id, **fields):
    """Update any fields on a job by id. Example: update_job(3, status='Applied', notes='Great role')"""
    allowed = {"title", "company", "location", "salary", "url", "date_applied",
               "resume_version", "notes", "h1b_status", "source", "status",
               "match_score", "matched_resume"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [job_id]
    with _connect() as conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", values)


def get_job(job_id):
    """Fetch a single job as a dict."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(status=None, company=None, resume_version=None):
    """List jobs with optional filters. Returns list of dicts."""
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")
    if resume_version:
        query += " AND resume_version = ?"
        params.append(resume_version)
    query += " ORDER BY date_scraped DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def search_jobs(query):
    """Search title, company, and notes. Returns list of dicts."""
    pattern = f"%{query}%"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE title LIKE ? OR company LIKE ? OR notes LIKE ? ORDER BY date_scraped DESC",
            (pattern, pattern, pattern),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_job(job_id):
    """Delete a job by id."""
    with _connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


def get_stats():
    """Return counts per status and per resume_version, plus the most recent scrape date."""
    with _connect() as conn:
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        ).fetchall()
        version_rows = conn.execute(
            "SELECT resume_version, COUNT(*) as count FROM jobs GROUP BY resume_version"
        ).fetchall()
        last_row = conn.execute(
            "SELECT MAX(date_scraped) as last FROM jobs"
        ).fetchone()
    return {
        "by_status": {r["status"]: r["count"] for r in status_rows},
        "by_resume_version": {r["resume_version"]: r["count"] for r in version_rows},
        "last_scraped": last_row["last"] if last_row else None,
    }


if __name__ == "__main__":
    init_db()

    # Smoke test
    added = add_job(
        title="Research Analyst",
        company="Brookings Institution",
        location="Washington, DC",
        url="https://brookings.edu/careers/test-job-123",
        source="manual_test",
    )
    print(f"Job added: {added}")

    jobs = list_jobs(status="New")
    print(f"Jobs with status 'New': {len(jobs)}")
    for j in jobs:
        print(f"  [{j['id']}] {j['title']} @ {j['company']} — {j['status']}")

    if jobs:
        job_id = jobs[0]["id"]
        update_job(job_id, status="Interested", notes="Great fit for EconPolicy resume")
        updated = get_job(job_id)
        print(f"Updated job: status={updated['status']}, notes={updated['notes']}")

    results = search_jobs("Brookings")
    print(f"Search 'Brookings': {len(results)} result(s)")

    stats = get_stats()
    print(f"Stats: {stats}")

    delete_job(jobs[0]["id"] if jobs else -1)
    print("Smoke test complete.")
