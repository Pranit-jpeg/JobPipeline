"""
U.S. Department of the Treasury scraper — USAJobs API filtered to Treasury.
Reuses the USAJobs API key from .env (USAJOBS_API_KEY).
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper
from scrapers.usajobs import USAJobsScraper, API_URL, KEYWORDS, GS_LOW, GS_HIGH, PAGE_SIZE


class TreasuryScraper(USAJobsScraper):
    COMPANY = "U.S. Department of the Treasury"
    SOURCE  = "treasury"

    def _fetch_page(self, keyword, page):
        params = {
            "Keyword":        keyword,
            "DepartmentCode": "TR",
            "PayGradeLow":    GS_LOW,
            "PayGradeHigh":   GS_HIGH,
            "ResultsPerPage": PAGE_SIZE,
            "PageNumber":     page,
            "WhoMayApply":    "public",
        }
        resp = requests.get(API_URL, params=params, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    db.init_db()
    TreasuryScraper().run()
