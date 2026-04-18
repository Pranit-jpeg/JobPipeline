"""
Brattle Group scraper — Greenhouse API (detected via network intercept).
Board slug: thebrattlegroup
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

API_URL = "https://boards-api.greenhouse.io/v1/boards/thebrattlegroup/jobs?content=true"

KEYWORDS = {
    "economist", "economic", "research analyst", "data analyst",
    "policy analyst", "quantitative", "research associate",
    "research scientist", "research fellow", "analyst",
}


class BrattleScraper(BaseScraper):
    COMPANY = "The Brattle Group"
    SOURCE  = "brattle"

    def scrape(self):
        resp = requests.get(API_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for job in data.get("jobs", []):
            title    = job.get("title", "").strip()
            if not title:
                continue
            if not any(kw in title.lower() for kw in KEYWORDS):
                continue
            location = job.get("location", {}).get("name", "Multiple Locations")
            jobs.append({
                "title":    title,
                "company":  self.COMPANY,
                "location": location,
                "url":      job.get("absolute_url", ""),
            })
        return jobs


if __name__ == "__main__":
    db.init_db()
    BrattleScraper().run()
