"""
Federal Reserve System scraper — uses the FRS Workday API.
All 12 Reserve Banks post to the same portal (rb.wd5.myworkdayjobs.com/FRS),
so this scraper captures relevant jobs across all districts.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import WorkdayScraper

_BANK_MAP = {
    "Boston":       "Federal Reserve Bank of Boston",
    "New York":     "Federal Reserve Bank of New York",
    "Philadelphia": "Federal Reserve Bank of Philadelphia",
    "Cleveland":    "Federal Reserve Bank of Cleveland",
    "Richmond":     "Federal Reserve Bank of Richmond",
    "Atlanta":      "Federal Reserve Bank of Atlanta",
    "Chicago":      "Federal Reserve Bank of Chicago",
    "St. Louis":    "Federal Reserve Bank of St. Louis",
    "Minneapolis":  "Federal Reserve Bank of Minneapolis",
    "Kansas City":  "Federal Reserve Bank of Kansas City",
    "Dallas":       "Federal Reserve Bank of Dallas",
    "San Francisco":"Federal Reserve Bank of San Francisco",
    "Washington":   "Federal Reserve Board of Governors",
}


def _company_from_location(location_text):
    for city, name in _BANK_MAP.items():
        if city in location_text:
            return name
    return "Federal Reserve System"


class FedReserveScraper(WorkdayScraper):
    COMPANY = "Federal Reserve System"
    SOURCE = "fed_reserve"
    WD_HOST = "rb.wd5.myworkdayjobs.com"
    WD_TENANT = "rb"
    WD_SITE = "FRS"

    def _build_job(self, path, job):
        loc = job.get("locationsText", "Unknown").strip()
        return {
            "title": job.get("title", "").strip(),
            "company": _company_from_location(loc),
            "location": loc,
            "url": self._job_base_url() + path,
        }


if __name__ == "__main__":
    db.init_db()
    FedReserveScraper().run()
