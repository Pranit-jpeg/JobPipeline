"""Uber (uber.com/careers) scraper.

Uber exposes a public REST search endpoint that returns clean structured
JSON — no Workday, no Playwright needed.

  POST https://www.uber.com/api/loadSearchJobsResults?localeCode=en
  Body: {"limit": N, "page": M, "params": {"location": [...], "department": [...]}}
  Header: x-csrf-token: <any non-empty>

We loop over a curated list of departments most likely to surface
entry-level analyst / data / research roles, paginate within each, and
return one job dict per posting (deduped by id). The base scraper's
existing entry-level / target-role / US-location / freshness filters do
the heavy lifting.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import db
from scrapers.base import BaseScraper

_API_URL = "https://www.uber.com/api/loadSearchJobsResults?localeCode=en"
_REFERER = "https://www.uber.com/us/en/careers/list/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.uber.com",
    "Referer": _REFERER,
    "User-Agent": _UA,
    # Any non-empty value satisfies Uber's CSRF check on the public search
    # endpoint; the bootstrap-from-cookie path isn't necessary here.
    "x-csrf-token": "x",
}

# Departments to query. Uber's department taxonomy is broad — these are
# the slices that historically surface MS-Econ-eligible roles (analyst,
# economist, research analyst, data analyst, business analyst). Broader
# than strictly necessary; existing keyword filter trims the noise.
_DEPARTMENTS = [
    "Data Science",
    "Engineering",          # surfaces "Software Engineer, Analytics" etc.
    "Operations",
    "Strategy",
    "Finance",
    "Marketing",            # surfaces marketing analyst / market research analyst
]

_PAGE_SIZE = 50
_MAX_PAGES_PER_DEPT = 4   # 50 * 4 = 200 cap, more than enough for any one dept


class UberScraper(BaseScraper):
    COMPANY = "Uber"
    SOURCE = "uber"
    # At Uber, "Data Scientist II" / "Engineer II" is L3-L4 (mid-level,
    # MS-new-grad eligible). Don't apply the Roman-numeral senior filter.
    # Senior + Staff + Lead etc. are still caught by the base exclude list.
    STRICT_LEVEL_FILTER = False

    def scrape(self):
        seen: dict[int, dict] = {}
        for dept in _DEPARTMENTS:
            for page in range(_MAX_PAGES_PER_DEPT):
                payload = {
                    "limit": _PAGE_SIZE,
                    "page": page,
                    "params": {
                        "location": [{"country": "USA"}],
                        "department": [dept],
                    },
                }
                try:
                    resp = requests.post(_API_URL, headers=_HEADERS, json=payload, timeout=15)
                    resp.raise_for_status()
                except requests.RequestException as e:
                    print(f"  [{self.SOURCE}] dept={dept!r} page={page} request failed: {e}")
                    break

                results = resp.json().get("data", {}).get("results") or []
                if not results:
                    break  # past the end

                for job in results:
                    jid = job.get("id")
                    if jid is None or jid in seen:
                        continue
                    seen[jid] = job

                if len(results) < _PAGE_SIZE:
                    break  # last page
                time.sleep(0.4)
            time.sleep(0.6)
        return [self._to_job_dict(j) for j in seen.values()]

    def _to_job_dict(self, job):
        loc = job.get("location") or {}
        location = self._format_location(loc, job.get("allLocations") or [])
        return {
            "title":       (job.get("title") or "").strip(),
            "company":     self.COMPANY,
            "location":    location,
            "url":         f"https://www.uber.com/global/en/careers/list/{job['id']}/",
            "date_posted": job.get("creationDate"),  # ISO 8601, parsed by base.is_fresh
        }

    @staticmethod
    def _format_location(primary: dict, all_locations: list) -> str:
        city = (primary.get("city") or "").strip()
        region = (primary.get("region") or "").strip()
        country = (primary.get("countryName") or primary.get("country") or "").strip()
        parts = [p for p in (city, region) if p]
        loc_str = ", ".join(parts) if parts else (country or "Unknown")
        # Mirror the "+N locations" suffix Workday/Meta scrapers produce when
        # a posting lives in multiple offices, so the dashboard display is
        # consistent across sources.
        extras = max(0, len(all_locations) - 1)
        if extras:
            loc_str = f"{loc_str} +{extras} location{'s' if extras > 1 else ''}"
        return loc_str


if __name__ == "__main__":
    db.init_db()
    UberScraper().run()
