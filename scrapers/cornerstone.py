"""
Cornerstone Research scraper — Workday portal.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import WorkdayScraper

KEYWORDS = [
    "research analyst",
    "analyst",
    "economist",
    "data analyst",
    "associate",
]


class CornerstoneScraper(WorkdayScraper):
    COMPANY    = "Cornerstone Research"
    SOURCE     = "cornerstone"
    WD_HOST    = "cornerstone.wd501.myworkdayjobs.com"
    WD_TENANT  = "cornerstone"
    WD_SITE    = "CornerstoneResearch_Careers"
    KEYWORDS   = KEYWORDS


if __name__ == "__main__":
    db.init_db()
    CornerstoneScraper().run()
