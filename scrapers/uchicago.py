"""
University of Chicago scraper — Workday portal (Research & Data roles).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import WorkdayScraper

KEYWORDS = [
    "research analyst",
    "data analyst",
    "policy analyst",
    "economist",
    "research associate",
]


class UChicagoScraper(WorkdayScraper):
    COMPANY   = "University of Chicago"
    SOURCE    = "uchicago"
    WD_HOST   = "uchicago.wd5.myworkdayjobs.com"
    WD_TENANT = "uchicago"
    WD_SITE   = "External"
    KEYWORDS  = KEYWORDS


if __name__ == "__main__":
    db.init_db()
    UChicagoScraper().run()
