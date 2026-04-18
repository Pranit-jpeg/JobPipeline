import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import WorkdayScraper


class RandScraper(WorkdayScraper):
    COMPANY = "RAND Corporation"
    SOURCE = "rand"
    WD_HOST = "rand.wd5.myworkdayjobs.com"
    WD_TENANT = "rand"
    WD_SITE = "External_Career_Site"


if __name__ == "__main__":
    db.init_db()
    RandScraper().run()
