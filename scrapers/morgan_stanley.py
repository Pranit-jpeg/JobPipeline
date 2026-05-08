"""Morgan Stanley scraper.

Morgan Stanley's careers run on Eightfold AI's PCSX platform. There's a
public REST search endpoint at:

  GET https://morganstanley.eightfold.ai/api/pcsx/search

Auth is a CSRF token tied to a Flask session cookie. To bootstrap:
  1. GET /careers — sets a `_vs` session cookie
  2. Send the cookie value as the `x-csrf-token` header on every API call

The default page size is 10 (we paginate `start=0, 10, 20, ...`). The
endpoint accepts `query`, `location`, `start`. We loop over a curated list
of search terms most likely to surface MS-Econ-eligible roles and dedupe
by position ID.

MS uses Roman-numeral level conventions ("Director II") that genuinely
indicate senior, so the conservative `STRICT_LEVEL_FILTER=True` default
applies — no override.
"""
import sys
import os
import time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import db
from scrapers.base import BaseScraper

_API   = "https://morganstanley.eightfold.ai/api/pcsx/search"
_SEED  = "https://morganstanley.eightfold.ai/careers"
_DOMAIN = "morganstanley.com"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

# Search terms that surface MS-Econ-eligible postings. Each is one API
# round-trip per page; broader terms cost more cycles but the job-ID dedupe
# means redundancy is cheap.
_QUERIES = [
    "data analyst",
    "research analyst",
    "financial analyst",
    "economist",
    "quantitative analyst",
    "policy analyst",
    "associate",         # research associate, equity research associate
    "data scientist",
]

_PAGE_SIZE = 10           # Eightfold's fixed default; doesn't honor larger sizes
_MAX_PAGES_PER_QUERY = 8  # 80 results per query is plenty before dedup + filter


class MorganStanleyScraper(BaseScraper):
    COMPANY = "Morgan Stanley"
    SOURCE = "morgan_stanley"

    def scrape(self):
        session = requests.Session()
        session.headers.update({"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})

        # Bootstrap: GET careers to seed the _vs cookie used as the CSRF token.
        try:
            session.get(_SEED, timeout=20)
        except requests.RequestException as e:
            print(f"  [{self.SOURCE}] failed to seed session: {e}")
            return []

        csrf = session.cookies.get("_vs")
        if not csrf:
            print(f"  [{self.SOURCE}] no _vs cookie returned — Eightfold may have rotated cookie names")
            return []

        api_headers = {
            "Accept": "application/json",
            "Referer": _SEED,
            "Origin": "https://morganstanley.eightfold.ai",
            "x-csrf-token": csrf,
        }

        seen: dict[int, dict] = {}
        for query in _QUERIES:
            for page in range(_MAX_PAGES_PER_QUERY):
                params = {
                    "domain":   _DOMAIN,
                    "query":    query,
                    "location": "",     # don't filter by location at API — base scraper handles US filtering
                    "start":    page * _PAGE_SIZE,
                }
                try:
                    r = session.get(_API, params=params, headers=api_headers, timeout=15)
                    r.raise_for_status()
                except requests.RequestException as e:
                    print(f"  [{self.SOURCE}] query={query!r} start={params['start']} failed: {e}")
                    break

                positions = (r.json().get("data") or {}).get("positions") or []
                if not positions:
                    break

                for pos in positions:
                    pid = pos.get("id")
                    if pid is None or pid in seen:
                        continue
                    seen[pid] = pos

                if len(positions) < _PAGE_SIZE:
                    break  # last page for this query
                time.sleep(0.4)
            time.sleep(0.6)

        return [self._to_job_dict(p) for p in seen.values()]

    def _to_job_dict(self, pos):
        locations = pos.get("locations") or pos.get("standardizedLocations") or []
        location = locations[0] if locations else "Unknown"
        if len(locations) > 1:
            extras = len(locations) - 1
            location = f"{location} +{extras} location{'s' if extras > 1 else ''}"
        return {
            "title":       (pos.get("name") or "").strip(),
            "company":     self.COMPANY,
            "location":    location,
            "url":         f"https://morganstanley.eightfold.ai/careers/job/{pos['id']}",
            "date_posted": self._format_ts(pos.get("postedTs") or pos.get("creationTs")),
        }

    @staticmethod
    def _format_ts(ts):
        """Eightfold stores postedTs as Unix seconds. Convert to ISO so the
        base.is_fresh date parser handles it.
        """
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError, OSError):
            return None


if __name__ == "__main__":
    db.init_db()
    MorganStanleyScraper().run()
