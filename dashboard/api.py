"""
JobPipeline REST API — Flask backend for the Kanban dashboard.

Endpoints:
  GET    /api/jobs           list jobs, filterable by ?status=&company=&resume_version=
  GET    /api/jobs/<id>      single job detail
  POST   /api/jobs           manually add a new job
  PUT    /api/jobs/<id>      update a job (status, notes, resume_version, date_applied, etc.)
  DELETE /api/jobs/<id>      delete a job
  GET    /api/stats          counts per status and per resume_version

Run:  python dashboard/api.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, abort, send_file
import db

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from generation import generate_application
from generation.utils import GENERATED_DIR

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _job_or_404(job_id):
    job = db.get_job(job_id)
    if job is None:
        abort(404, description=f"Job {job_id} not found.")
    return job


def _ok(data=None, message=None, status=200):
    payload = {}
    if data is not None:
        payload["data"] = data
    if message:
        payload["message"] = message
    return jsonify(payload), status


# ── CORS (allow the frontend served from any local origin) ────────────────────

@app.after_request
def _cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.route("/api/jobs", methods=["OPTIONS"])
@app.route("/api/jobs/<int:job_id>", methods=["OPTIONS"])
def _options(**kwargs):
    return _ok()


# ── GET /api/jobs ─────────────────────────────────────────────────────────────

@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    status         = request.args.get("status")
    company        = request.args.get("company")
    resume_version = request.args.get("resume_version")
    q              = request.args.get("q")

    if q:
        jobs = db.search_jobs(q)
    else:
        jobs = db.list_jobs(status=status, company=company,
                            resume_version=resume_version)
    return _ok(jobs)


# ── GET /api/jobs/<id> ────────────────────────────────────────────────────────

@app.route("/api/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):
    return _ok(_job_or_404(job_id))


# ── POST /api/jobs ────────────────────────────────────────────────────────────

@app.route("/api/jobs", methods=["POST"])
def add_job():
    body = request.get_json(silent=True) or {}

    required = ("title", "company", "location", "url")
    missing = [f for f in required if not body.get(f)]
    if missing:
        abort(400, description=f"Missing required fields: {', '.join(missing)}")

    added = db.add_job(
        title=body["title"],
        company=body["company"],
        location=body["location"],
        url=body["url"],
        source=body.get("source", "manual"),
        salary=body.get("salary"),
    )
    if not added:
        abort(409, description="A job with that URL already exists.")

    # Return the newly created job
    jobs = db.search_jobs(body["url"])
    new_job = jobs[0] if jobs else None
    return _ok(new_job, message="Job added.", status=201)


# ── PUT /api/jobs/<id> ────────────────────────────────────────────────────────

@app.route("/api/jobs/<int:job_id>", methods=["PUT"])
def update_job(job_id):
    _job_or_404(job_id)
    body = request.get_json(silent=True) or {}

    allowed = {"title", "company", "location", "salary", "url",
               "date_applied", "resume_version", "notes",
               "h1b_status", "source", "status"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        abort(400, description="No valid fields to update.")

    # Validate status if provided
    if "status" in updates and updates["status"] not in db.STATUSES:
        abort(400, description=f"Invalid status. Choose from: {', '.join(db.STATUSES)}")

    # If the client is moving status -> Dismissed via PUT, route through the
    # dismiss helper so auto_dismissed=0 (user decision). Other fields update
    # normally.
    if updates.get("status") == "Dismissed":
        db.dismiss_job(job_id, by_user=True)
        other = {k: v for k, v in updates.items() if k != "status"}
        if other:
            db.update_job(job_id, **other)
    else:
        db.update_job(job_id, **updates)
    return _ok(db.get_job(job_id), message="Job updated.")


# ── DELETE /api/jobs/<id> ─────────────────────────────────────────────────────
#
# Soft-delete: mark the job as 'Dismissed' instead of removing the row.
# Keeping the row preserves the UNIQUE(url) constraint, so the next scrape
# won't re-surface a job the user already rejected. Hard-delete can be forced
# with ?hard=1 for admin use.

@app.route("/api/jobs/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    _job_or_404(job_id)
    if request.args.get("hard") == "1":
        db.delete_job(job_id)
        return _ok(message=f"Job {job_id} permanently deleted.")
    db.dismiss_job(job_id, by_user=True)
    return _ok(message=f"Job {job_id} dismissed.")


# ── GET /api/stats ────────────────────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    stats = db.get_stats()

    # Ensure all statuses appear even with 0 count
    by_status = {s: 0 for s in db.STATUSES}
    by_status.update(stats.get("by_status", {}))

    # Ensure all resume versions appear; skip None keys (unassigned jobs)
    by_resume = {v: 0 for v in db.RESUME_VERSIONS}
    for k, v in stats.get("by_resume_version", {}).items():
        if k is not None:
            by_resume[k] = v

    all_jobs   = db.list_jobs()
    active     = [j for j in all_jobs if j["status"] != "Dismissed"]
    applied    = [j for j in active if j["status"] in ("Applied", "Interview", "Offer")]
    interviews = [j for j in active if j["status"] == "Interview"]
    response_rate = (
        round(len(interviews) / len(applied) * 100, 1) if applied else 0.0
    )

    return _ok({
        "by_status":         by_status,
        "by_resume_version": by_resume,
        "total_jobs":        len(active),
        "applied_count":     len(applied),
        "interview_count":   len(interviews),
        "response_rate":     response_rate,
        "last_scraped":      stats.get("last_scraped"),
    })


# ── POST /api/jobs/<id>/generate ──────────────────────────────────────────────

@app.route("/api/jobs/<int:job_id>/generate", methods=["POST", "OPTIONS"])
def generate_for_job(job_id):
    if request.method == "OPTIONS":
        return _ok()
    job = _job_or_404(job_id)
    try:
        result = generate_application(job)
    except FileNotFoundError as e:
        abort(400, description=str(e))
    except RuntimeError as e:
        abort(500, description=str(e))
    except Exception as e:
        abort(500, description=f"Generation failed: {e}")

    def _rel(p):
        if not p:
            return None
        return os.path.relpath(p, GENERATED_DIR).replace("\\", "/")

    return _ok({
        "resume_version": result["resume_version"],
        "body_ordering": result["body_ordering"],
        "used_passion_statement": result["used_passion_statement"],
        "changes_summary": result.get("changes_summary", []),
        "ats_keywords": result.get("ats_keywords", []),
        "resume_audit_notes": result.get("resume_audit_notes", []),
        "cover_letter_audit_notes": result.get("cover_letter_audit_notes", []),
        "jd_chars": result.get("jd_chars", 0),
        "resume_tightness": result.get("resume_tightness", 0),
        "cover_letter_tightness": result.get("cover_letter_tightness", 0),
        "cover_letter_preview": result["cover_letter_preview"],
        "resume_pdf_rel": _rel(result["resume_pdf"]),
        "cover_letter_pdf_rel": _rel(result["cover_letter_pdf"]),
        "resume_docx_rel": _rel(result["resume_docx"]),
        "cover_letter_docx_rel": _rel(result["cover_letter_docx"]),
        "pdf_error": result["pdf_error"],
    })


# ── GET /api/generated/<path> — serve the produced files ─────────────────────

@app.route("/api/generated/<path:relpath>", methods=["GET"])
def serve_generated(relpath):
    abs_path = os.path.abspath(os.path.join(GENERATED_DIR, relpath))
    # Path-traversal guard: must stay inside GENERATED_DIR
    if not abs_path.startswith(os.path.abspath(GENERATED_DIR) + os.sep):
        abort(403)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_file(abs_path, as_attachment=True)


# ── error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(500)
def _error(e):
    return jsonify({"error": e.description}), e.code


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    print("\nRegistered routes:")
    for rule in sorted(app.url_map.iter_rules(), key=str):
        print(f"  {sorted(rule.methods)} {rule}")
    print("\nJobPipeline API running at http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
