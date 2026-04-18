"""
USAJobs.gov scraper — official USAJobs REST API.

SETUP (one-time):
  1. Get a free API key at https://developer.usajobs.gov/
  2. Copy .env.example to .env and fill in:
       USAJOBS_API_KEY=your_key_here

Searches GS-5 through GS-11 positions (entry to mid-level) across all locations.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import db
from scrapers.base import BaseScraper

API_URL = "https://data.usajobs.gov/api/search"

KEYWORDS = [
    "economist",
    "economic analyst",
    "policy analyst",
    "research analyst",
    "data analyst",
]

GS_LOW = 5
GS_HIGH = 11
PAGE_SIZE = 100


class USAJobsScraper(BaseScraper):
    COMPANY = "U.S. Federal Government"
    SOURCE = "usajobs"

    def _headers(self):
        api_key = os.environ.get("USAJOBS_API_KEY", "")
        email = os.environ.get("USAJOBS_EMAIL", "choudhary.pra@northeastern.edu")
        if not api_key:
            raise RuntimeError(
                "USAJobs API key not set.\n"
                "  1. Register free at https://developer.usajobs.gov/\n"
                "  2. Add to .env in the project root: USAJOBS_API_KEY=your_key_here"
            )
        return {
            "Host": "data.usajobs.gov",
            "User-Agent": email,
            "Authorization-Key": api_key,
        }

    def _fetch_page(self, keyword, page):
        params = {
            "Keyword": keyword,
            "PayGradeLow": GS_LOW,
            "PayGradeHigh": GS_HIGH,
            "ResultsPerPage": PAGE_SIZE,
            "PageNumber": page,
            "WhoMayApply": "public",
        }
        resp = requests.get(API_URL, params=params, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def scrape(self):
        jobs = {}
        for keyword in KEYWORDS:
            page = 1
            while True:
                try:
                    data = self._fetch_page(keyword, page)
                except requests.RequestException as e:
                    print(f"  [usajobs] Request failed for '{keyword}' page {page}: {e}")
                    break

                search = data.get("SearchResult", {})
                items = search.get("SearchResultItems", [])
                if not items:
                    break

                for item in items:
                    desc = item.get("MatchedObjectDescriptor", {})
                    pos_uri = desc.get("PositionURI", "")
                    if not pos_uri or pos_uri in jobs:
                        continue

                    title = desc.get("PositionTitle", "").strip()
                    org = desc.get("OrganizationName", "Federal Agency").strip()

                    locs = desc.get("PositionLocation", [])
                    location = locs[0].get("LocationName", "USA") if locs else "USA"

                    remun = desc.get("PositionRemuneration", [])
                    salary = None
                    if remun:
                        lo = remun[0].get("MinimumRange", "")
                        hi = remun[0].get("MaximumRange", "")
                        interval = remun[0].get("RateIntervalCode", "")
                        if lo and hi:
                            try:
                                salary = f"${float(lo):,.0f}–${float(hi):,.0f} {interval}".strip()
                            except ValueError:
                                pass

                    date_posted = desc.get("PublicationStartDate", "")
                    if date_posted:
                        date_posted = date_posted[:10]  # keep YYYY-MM-DD

                    jobs[pos_uri] = {
                        "title":       title,
                        "company":     org,
                        "location":    location,
                        "url":         pos_uri,
                        "salary":      salary,
                        "date_posted": date_posted or None,
                    }

                total = int(search.get("SearchResultCountAll", 0))
                if page * PAGE_SIZE >= total:
                    break
                page += 1
                time.sleep(0.5)

            time.sleep(0.5)

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    USAJobsScraper().run()
