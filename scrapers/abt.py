"""
Abt Associates (Abt Global) scraper — uses Oracle Cloud HCM REST API.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

ORACLE_BASE = "https://egpy.fa.us2.oraclecloud.com"
SITE_NUMBER = "CX_3001"
JOB_URL_BASE = f"{ORACLE_BASE}/hcmUI/CandidateExperience/en/sites/JoinAbt/requisitions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

KEYWORDS = [
    "analyst",
    "economist",
    "research",
    "policy",
    "evaluation",
    "data",
]


class AbtScraper(BaseScraper):
    COMPANY = "Abt Associates"
    SOURCE = "abt"

    def _fetch_keyword(self, keyword, offset=0, limit=25):
        url = (
            f"{ORACLE_BASE}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
            f"?expand=requisitionList.secondaryLocations"
            f"&onlyData=true"
            f"&finder=findReqs;siteNumber={SITE_NUMBER},keyword={requests.utils.quote(keyword)},"
            f"limit={limit},offset={offset},sortBy=POSTING_DATES_DESC"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"  [abt] Request failed for '{keyword}': {e}")
            return {}

    def scrape(self):
        seen_ids = set()
        jobs = []

        for keyword in KEYWORDS:
            offset = 0
            limit = 25
            while True:
                data = self._fetch_keyword(keyword, offset=offset, limit=limit)
                items = data.get("items", [])
                if not items:
                    break

                search_result = items[0]
                reqs = search_result.get("requisitionList", [])
                total = search_result.get("TotalJobsCount", 0)

                for req in reqs:
                    job_id = str(req.get("Id", ""))
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title = req.get("Title", "").strip()
                    location = req.get("PrimaryLocation", "Unknown").strip()
                    url = f"{JOB_URL_BASE}/{job_id}"

                    jobs.append({
                        "title": title,
                        "company": self.COMPANY,
                        "location": location,
                        "url": url,
                    })

                offset += limit
                if offset >= total:
                    break
                time.sleep(0.4)

            time.sleep(0.6)

        return jobs


if __name__ == "__main__":
    db.init_db()
    AbtScraper().run()
