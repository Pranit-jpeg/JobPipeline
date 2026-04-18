"""
S&P Global careers scraper — Workday CXS API (public, no auth required).
Tenant: spgi  |  Site: SPGI_Careers  |  Host: spgi.wd5.myworkdayjobs.com
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import WorkdayScraper


class SPGlobalScraper(WorkdayScraper):
    COMPANY   = "S&P Global"
    SOURCE    = "sp_global"
    WD_HOST   = "spgi.wd5.myworkdayjobs.com"
    WD_TENANT = "spgi"
    WD_SITE   = "SPGI_Careers"
    KEYWORDS  = [
        "economist",
        "research analyst",
        "policy analyst",
        "data analyst",
        "quantitative analyst",
    ]


if __name__ == "__main__":
    db.init_db()
    SPGlobalScraper().run()
