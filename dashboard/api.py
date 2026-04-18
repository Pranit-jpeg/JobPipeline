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

from flask import Flask, jsonify, request, abort
import db

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import anthropic
import requests as _requests
from bs4 import BeautifulSoup

_RESUME_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resumes")
_RESUME_FILES = {
    "EconPolicy":        "econ_policy.txt",
    "FinanceConsulting": "finance_consulting.txt",
    "DataAnalyst":       "data_analyst.txt",
    "ResearchAnalyst":   "research_analyst.txt",
}

def _fetch_jd(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = _requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
        return "\n".join(lines)[:5000]
    except Exception:
        return ""

def _load_resume(rv_key):
    filename = _RESUME_FILES.get(rv_key)
    if not filename:
        return None
    path = os.path.join(_RESUME_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

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

    db.update_job(job_id, **updates)
    return _ok(db.get_job(job_id), message="Job updated.")


# ── DELETE /api/jobs/<id> ─────────────────────────────────────────────────────

@app.route("/api/jobs/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    _job_or_404(job_id)
    db.delete_job(job_id)
    return _ok(message=f"Job {job_id} deleted.")


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
    applied    = [j for j in all_jobs if j["status"] in ("Applied", "Interview", "Offer")]
    interviews = [j for j in all_jobs if j["status"] == "Interview"]
    response_rate = (
        round(len(interviews) / len(applied) * 100, 1) if applied else 0.0
    )

    return _ok({
        "by_status":         by_status,
        "by_resume_version": by_resume,
        "total_jobs":        len(all_jobs),
        "applied_count":     len(applied),
        "interview_count":   len(interviews),
        "response_rate":     response_rate,
        "last_scraped":      stats.get("last_scraped"),
    })


# ── POST /api/jobs/<id>/tailor ────────────────────────────────────────────────

@app.route("/api/jobs/<int:job_id>/tailor", methods=["POST", "OPTIONS"])
def tailor_job(job_id):
    if request.method == "OPTIONS":
        return _ok()
    job = _job_or_404(job_id)

    # Prefer user-set resume version, then AI-matched, then default
    rv = job.get("resume_version") or job.get("matched_resume") or "ResearchAnalyst"

    resume_text = _load_resume(rv)
    if not resume_text:
        abort(400, description=f"Resume file for '{rv}' not found.")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        abort(500, description="ANTHROPIC_API_KEY not configured on the server.")

    description = _fetch_jd(job.get("url", ""))

    job_context = (
        f"Job Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job.get('location', '')}"
    )
    if description:
        job_context += f"\n\nJob Description:\n{description}"
    else:
        job_context += "\n\n(Job description unavailable — working from title and company only.)"

    prompt = f"""You are helping a recent MS Economics graduate (F-1/OPT, graduating May 2026, ~19 months total work experience) tailor their resume and write a cover letter for a specific job.

JOB:
{job_context}

RESUME ({rv}):
{resume_text[:3500]}

TASK 1 — KEYWORD SUGGESTIONS:
Identify 5-6 specific keywords or phrases from the job description that are absent or under-represented in the resume. For each one, suggest exactly where and how to weave it into an existing bullet (reference the role/bullet specifically). Be concrete and actionable — no vague advice.

TASK 2 — COVER LETTER:
Write a professional cover letter (~250 words, 3 paragraphs). Hard rules:
- Do NOT open with "I" as the first word
- Do NOT use "excited", "thrilled", "passionate", or "perfect fit"
- Lead with a specific accomplishment or skill match, not a story about yourself
- Reference concrete details from the job posting (specific tools, team focus, mission)
- Sound like a thoughtful human, not a template
- Tone: confident, direct, professional — not stiff or formal
- End with a brief, non-pushy call to action
- Sign off as: Pranit Choudhary

Respond ONLY with valid JSON and no extra text:
{{
  "resume_version": "{rv}",
  "keywords": [
    {{"phrase": "...", "suggestion": "..."}}
  ],
  "cover_letter": "full cover letter text here, with \\n for paragraph breaks"
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            return _ok(data)
        abort(500, description="Malformed AI response — could not parse JSON.")
    except anthropic.APIError as e:
        abort(500, description=f"Claude API error: {e}")
    except json.JSONDecodeError as e:
        abort(500, description=f"JSON parse error: {e}")


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
