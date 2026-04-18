"""
UChicago Becker Friedman Institute (BFI) scraper — Greenhouse API.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

GREENHOUSE_BOARD = "bfiprep"
API_URL = f"https://boards-api.greenhouse.io/v1/boards/{GREENHOUSE_BOARD}/jobs?content=true"


class BFIScraper(BaseScraper):
    COMPANY = "UChicago Becker Friedman Institute"
    SOURCE  = "bfi"

    def scrape(self):
        resp = requests.get(API_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for job in data.get("jobs", []):
            location = job.get("location", {}).get("name", "Chicago, IL")
            jobs.append({
                "title":    job.get("title", "").strip(),
                "company":  self.COMPANY,
                "location": location,
                "url":      job.get("absolute_url", ""),
            })
        return jobs


if __name__ == "__main__":
    db.init_db()
    BFIScraper().run()
