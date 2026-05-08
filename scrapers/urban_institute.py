import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import WorkdayScraper


class UrbanInstituteScraper(WorkdayScraper):
    COMPANY = "Urban Institute"
    SOURCE = "urban_institute"
    WD_HOST = "urban.wd115.myworkdayjobs.com"
    WD_TENANT = "urban"
    WD_SITE = "Urban-Careers"

    def _build_job(self, path, job):
        loc = job.get("locationsText", "Washington, DC").strip()
        # Workday sometimes embeds company name in location text — strip it
        if "Urban Institute" in loc:
            loc = "Washington, DC"
        return {
            "title": job.get("title", "").strip(),
            "company": self.COMPANY,
            "location": loc,
            "url": self._job_base_url() + path,
        }


if __name__ == "__main__":
    db.init_db()
    UrbanInstituteScraper().run()
