"""
NYC Government jobs scraper — NYC Open Data API (no API key required).
Dataset: NYC Jobs  https://data.cityofnewyork.us/resource/kpav-sd4t.json
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

API_URL = "https://data.cityofnewyork.us/resource/kpav-sd4t.json"
JOB_URL  = "https://cityjobs.nyc.gov/job/"

KEYWORDS = [
    "economist",
    "economic analyst",
    "policy analyst",
    "research analyst",
    "data analyst",
    "quantitative",
    "research associate",
]


class NYCGovScraper(BaseScraper):
    COMPANY = "NYC Government"
    SOURCE  = "nyc_gov"

    def _fetch(self, keyword):
        params = {"$q": keyword, "$limit": 50, "$order": "posting_date DESC"}
        try:
            resp = requests.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"  [nyc_gov] Request failed for '{keyword}': {e}")
            return []

    def scrape(self):
        jobs = {}
        for keyword in KEYWORDS:
            for item in self._fetch(keyword):
                job_id = str(item.get("job_id", "")).strip()
                if not job_id:
                    continue
                url = item.get("link_to_posting") or f"{JOB_URL}{job_id}"
                if url in jobs:
                    continue

                title    = item.get("business_title", "").strip()
                agency   = item.get("agency", "NYC Government").strip()
                location = (item.get("work_location") or "New York, NY").strip()

                salary = None
                sal_from = item.get("salary_range_from", "")
                sal_to   = item.get("salary_range_to", "")
                freq     = item.get("salary_frequency", "")
                if sal_from and sal_to:
                    try:
                        salary = f"${float(sal_from):,.0f}–${float(sal_to):,.0f} {freq}".strip()
                    except ValueError:
                        pass

                date_posted = item.get("posting_date", "")
                if date_posted:
                    date_posted = date_posted[:10]  # keep YYYY-MM-DD

                if title:
                    jobs[url] = {
                        "title":       title,
                        "company":     agency,
                        "location":    location,
                        "url":         url,
                        "salary":      salary,
                        "date_posted": date_posted or None,
                    }
            time.sleep(0.4)

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    NYCGovScraper().run()
