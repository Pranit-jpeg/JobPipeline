"""
USDA Economic Research Service (ERS) scraper — USAJobs API filtered to ERS.
Reuses the USAJobs API key from .env (USAJOBS_API_KEY).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.usajobs import USAJobsScraper, API_URL, KEYWORDS, GS_LOW, GS_HIGH, PAGE_SIZE


class USDAScraper(USAJobsScraper):
    COMPANY = "USDA Economic Research Service"
    SOURCE  = "usda_ers"

    def _fetch_page(self, keyword, page):
        params = {
            "Keyword":        keyword,
            "AgencyCode":     "AG18",   # ERS agency code on USAJobs
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
    USDAScraper().run()
