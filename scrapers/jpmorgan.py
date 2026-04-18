"""
JPMorgan Chase careers scraper — Oracle HCM public REST API.
No authentication required; the same endpoint the careers page calls.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

BASE_API = (
    "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/"
    "recruitingCEJobRequisitions"
)
JOB_URL_TPL = (
    "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/"
    "CX_1001/requisitions/{job_id}"
)
HEADERS   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

KEYWORDS  = ["research analyst", "economist", "quantitative analyst",
             "policy analyst", "data analyst"]
PAGE_SIZE = 25

def _is_relevant(title):
    return bool(title)  # entry-level filter handled centrally in BaseScraper.run()


class JPMorganScraper(BaseScraper):
    COMPANY = "JPMorgan Chase"
    SOURCE  = "jpmorgan"

    def _fetch(self, keyword, offset):
        params = {
            "onlyData": "true",
            "expand":   "requisitionList.workLocation,requisitionList.secondaryLocations,requisitionList.PostedDate",
            "finder": (
                f'findReqs;siteNumber=CX_1001,'
                f'facetsList=LOCATIONS,'
                f'limit={PAGE_SIZE},'
                f'offset={offset},'
                f'keyword="{keyword}",'
                f'sortBy=RELEVANCY'
            ),
        }
        try:
            r = requests.get(BASE_API, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  [jpmorgan] Request failed for '{keyword}': {e}")
            return None

    def scrape(self):
        jobs = {}
        for keyword in KEYWORDS:
            offset = 0
            while True:
                data = self._fetch(keyword, offset)
                if not data:
                    break
                items = data.get("items", [])
                item = items[0] if items else {}
                req_list = item.get("requisitionList", [])
                if not req_list:
                    break

                for job in req_list:
                    job_id = job.get("Id")
                    if not job_id:
                        continue
                    url = JOB_URL_TPL.format(job_id=job_id)
                    if url in jobs:
                        continue
                    title = job.get("Title", "").strip()
                    if not title or not _is_relevant(title):
                        continue

                    raw_date = job.get("PostedDate") or job.get("StartDate") or ""
                    date_posted = raw_date[:10] if raw_date else None

                    jobs[url] = {
                        "title":       title,
                        "company":     self.COMPANY,
                        "location":    job.get("PrimaryLocation", "United States"),
                        "url":         url,
                        "date_posted": date_posted,
                    }

                total = int(item.get("TotalJobsCount") or 0)
                offset += PAGE_SIZE
                if offset >= total:
                    break
                time.sleep(0.5)
            time.sleep(0.5)

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    JPMorganScraper().run()
