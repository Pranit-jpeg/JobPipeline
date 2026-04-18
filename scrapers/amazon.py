"""
Amazon jobs scraper — public jobs search JSON API.
Searches US economist, economic, policy analyst, research analyst roles.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

API_URL = "https://www.amazon.jobs/en/search.json"
BASE_URL = "https://www.amazon.jobs"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

KEYWORDS  = ["economist", "economic", "policy analyst", "research analyst", "data analyst"]
PAGE_SIZE = 100

def _is_relevant(job):
    if job.get("is_intern"):
        return False
    if "intern" in job.get("job_schedule_type", "").lower():
        return False
    return True


def _location(job):
    parts = [p for p in [job.get("city", ""), job.get("state", "")] if p]
    country = job.get("country_code", "")
    if country and country not in ("USA", "US"):
        parts.append(country)
    return ", ".join(parts) if parts else "United States"


class AmazonScraper(BaseScraper):
    COMPANY = "Amazon"
    SOURCE  = "amazon"

    def _fetch(self, keyword, offset):
        params = {
            "base_query":   keyword,
            "loc_query":    "",
            "job_count":    PAGE_SIZE,
            "offset":       offset,
            "result_limit": PAGE_SIZE,
        }
        try:
            r = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  [amazon] Request failed for '{keyword}': {e}")
            return None

    def scrape(self):
        jobs = {}
        for keyword in KEYWORDS:
            offset = 0
            while True:
                data = self._fetch(keyword, offset)
                if not data:
                    break
                raw_jobs = data.get("jobs", [])
                if not raw_jobs:
                    break

                for job in raw_jobs:
                    path = job.get("job_path", "")
                    if not path or path in jobs or not _is_relevant(job):
                        continue
                    if job.get("country_code", "") not in ("USA", "US", ""):
                        continue
                    raw_date = job.get("posted_date") or job.get("updated_time") or ""
                    date_posted = raw_date[:10] if raw_date else None

                    jobs[path] = {
                        "title":       job.get("title", "").strip(),
                        "company":     job.get("company_name", self.COMPANY).strip(),
                        "location":    _location(job),
                        "url":         BASE_URL + path,
                        "date_posted": date_posted,
                    }

                total = int(data.get("hits", 0))
                offset += PAGE_SIZE
                if offset >= total:
                    break
                time.sleep(0.5)
            time.sleep(0.5)

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    AmazonScraper().run()
