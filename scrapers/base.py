import sys
import os
import re
import time
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from h1b_sponsors import get_h1b_status

# ── Entry-level filter ────────────────────────────────────────────────────────

MAX_AGE_HOURS = 36

# Substrings that disqualify a title as too senior.
# Titles are padded with spaces so " lead " won't match "leadership".
_EXCLUDE_TERMS = [
    "senior", " sr.", "(sr)",
    "lead ",
    "principal",
    "director",
    " manager",
    "vice president", " vp ", " vp,",
    "chief ",
    "head of",
    "managing",
    "executive director", "executive vice",
    "associate director", "associate vp", "associate vice",
    " ii ", " iii ", " iv ",
]


def is_entry_level(title: str) -> bool:
    """Return True if the title looks like an entry-level or early-career role."""
    t = f" {title.lower()} "
    return not any(term in t for term in _EXCLUDE_TERMS)


def _parse_date_posted(s):
    """Parse a date/datetime string to a UTC-aware datetime, or None on failure."""
    if not s:
        return None
    s = str(s).strip()
    # Strip common timezone suffixes before parsing
    s = re.sub(r'(Z|[+-]\d{2}:?\d{2})$', '', s)
    s = s[:26]  # cap at microsecond precision
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_fresh(date_posted_str) -> bool:
    """Return True if the posting is within MAX_AGE_HOURS, or if no date is known."""
    if not date_posted_str:
        return True
    dt = _parse_date_posted(date_posted_str)
    if dt is None:
        return True
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    return age_hours <= MAX_AGE_HOURS


# ── HTTP helpers ──────────────────────────────────────────────────────────────

_WD_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

DEFAULT_KEYWORDS = [
    "economist",
    "research analyst",
    "data analyst",
    "policy analyst",
    "quantitative analyst",
    "research associate",
]


class BaseScraper:
    COMPANY = "Unknown"
    SOURCE = "unknown"
    IGNORE_FRESHNESS = False  # set True for feeds where postings are intentionally weeks old

    def scrape(self):
        """Return a list of job dicts with keys: title, company, location, url, salary (optional)."""
        raise NotImplementedError

    def run(self):
        """Scrape jobs and save new ones to the database. Prints a summary."""
        print(f"[{self.SOURCE}] Scraping {self.COMPANY}...")
        try:
            jobs = self.scrape()
        except Exception as e:
            print(f"[{self.SOURCE}] ERROR: {e}")
            return 0

        skipped_senior = 0
        skipped_stale  = 0
        new_count      = 0

        for job in jobs:
            title = job["title"]

            if not is_entry_level(title):
                skipped_senior += 1
                continue

            date_posted = job.get("date_posted")
            if not self.IGNORE_FRESHNESS and not is_fresh(date_posted):
                skipped_stale += 1
                continue

            company    = job.get("company", self.COMPANY)
            h1b_status = get_h1b_status(company)

            added = db.add_job(
                title=title,
                company=company,
                location=job["location"],
                url=job["url"],
                source=self.SOURCE,
                salary=job.get("salary"),
                date_posted=date_posted,
                h1b_status=h1b_status,
            )
            if added:
                new_count += 1

        print(
            f"[{self.SOURCE}] Done — {new_count} new job(s) added "
            f"({len(jobs)} found, {skipped_senior} senior filtered, "
            f"{skipped_stale} stale filtered)."
        )
        return new_count


class WorkdayScraper(BaseScraper):
    """Base class for any org that uses Workday (myworkdayjobs.com)."""
    WD_HOST = ""    # e.g. "rb.wd5.myworkdayjobs.com"
    WD_TENANT = ""  # e.g. "rb"
    WD_SITE = ""    # e.g. "FRS"
    KEYWORDS = DEFAULT_KEYWORDS

    def _api_url(self):
        return f"https://{self.WD_HOST}/wday/cxs/{self.WD_TENANT}/{self.WD_SITE}/jobs"

    def _job_base_url(self):
        return f"https://{self.WD_HOST}/{self.WD_SITE}"

    def _fetch_keyword(self, keyword):
        url = self._api_url()
        headers = {**_WD_HEADERS, "Referer": self._job_base_url()}
        jobs = {}
        offset = 0
        limit = 20
        while True:
            payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": keyword}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{self.SOURCE}] Request failed for '{keyword}': {e}")
                break
            data = resp.json()
            postings = data.get("jobPostings", [])
            if not postings:
                break
            for job in postings:
                path = job.get("externalPath", "")
                if path and path not in jobs:
                    jobs[path] = job
            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break
            time.sleep(0.4)
        return jobs

    def _build_job(self, path, job):
        return {
            "title":       job.get("title", "").strip(),
            "company":     self.COMPANY,
            "location":    job.get("locationsText", "Unknown").strip(),
            "url":         self._job_base_url() + path,
            "date_posted": job.get("postedOn"),  # Workday returns ISO date string
        }

    def scrape(self):
        all_jobs = {}
        for keyword in self.KEYWORDS:
            found = self._fetch_keyword(keyword)
            all_jobs.update(found)
            time.sleep(0.6)
        return [self._build_job(path, job) for path, job in all_jobs.items()]
