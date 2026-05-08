"""Meta (metacareers.com) scraper.

Meta does NOT use Workday — its careers UI is a custom React app backed by
an authenticated GraphQL endpoint. Direct API replication is not tractable
without a full session bootstrap (the GraphQL payload requires `__hs`,
`__rev`, `__dyn` tokens that rotate and are tied to the page bundle).

So we drive a headless browser instead, the same approach the JD fetcher
already uses. Strategy:

- Visit a curated list of team-filter URLs, each sorted by "Newest".
- Each filter page renders the 10 most recent postings for that team as
  `<a href="/profile/job_details/<id>">` cards. Pagination requires
  interactions that don't survive headless, but 10 newest per team is more
  than enough for daily scraping with a 36-hour freshness window — Meta's
  Research / Data & Analytics teams typically post a handful per week.
- Aggregate, dedupe by job ID, then let `BaseScraper.run` apply the usual
  entry-level / target-role / US-location / freshness filters.
"""
import sys
import os
import time
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

# Team filters most likely to surface analyst / economist / research-analyst
# postings. Meta's filter values are case- and ampersand-sensitive — these
# match the labels exposed in the careers UI sidebar.
_TEAM_FILTERS = [
    "Research",
    "Data %26 Analytics",        # URL-encoded "Data & Analytics"
    "AI Research",
    "Artificial Intelligence",
]

_BASE = "https://www.metacareers.com"
_LIST_URL = _BASE + "/jobs?teams[0]={team}&sort_by_new=true"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_JOB_ID_RE = re.compile(r"/profile/job_details/(\d+)")

# Lines that look like a location string. Order of card lines isn't
# stable — for some cards the team name appears before the location, so
# we pick the first line whose shape matches a city or "Multiple Locations".
_US_STATE_TWO = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    "MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|"
    "VA|WA|WV|WI|WY|DC"
)
_LOCATION_RE = re.compile(
    r"^("
    rf"[A-Z][A-Za-z .'\-]+,\s*({_US_STATE_TWO})(\s*\+\d+\s*locations?)?"   # Menlo Park, CA  /  Bellevue, WA +5 locations
    r"|Remote(\s*[-,]\s*US)?"
    r"|Multiple Locations?"
    r"|[A-Z][A-Za-z .'\-]+,\s*[A-Z][A-Za-z .'\-]+(\s*\+\d+\s*locations?)?"  # Dublin, Ireland (non-US fallback — base scraper rejects later)
    r")\s*$"
)


class MetaScraper(BaseScraper):
    COMPANY = "Meta"
    SOURCE = "meta"

    # Meta lists undated cards; freshness filtering happens inside BaseScraper
    # only when the scraper sets a date_posted. We don't have one from the
    # listing card, so we rely on `&sort_by_new=true` + IGNORE_FRESHNESS=False
    # with no date_posted (which BaseScraper treats as "fresh by default").
    IGNORE_FRESHNESS = True  # Meta's listing cards have no posted-date field

    def scrape(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print(f"  [{self.SOURCE}] playwright not installed — skipping")
            return []

        seen: dict[str, dict] = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(
                    user_agent=_UA,
                    viewport={"width": 1400, "height": 900},
                )
                for team in _TEAM_FILTERS:
                    url = _LIST_URL.format(team=team)
                    cards = self._scrape_one_filter(ctx, url, team)
                    for c in cards:
                        # Dedupe by job ID — same posting may appear under
                        # multiple team filters.
                        seen.setdefault(c["job_id"], c)
                    time.sleep(0.7)
            finally:
                browser.close()

        return [self._to_job_dict(c) for c in seen.values()]

    def _scrape_one_filter(self, ctx, url, team):
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)
            anchors = page.eval_on_selector_all(
                "a[href*='/profile/job_details/']",
                "els => els.map(e => ({"
                "href: e.getAttribute('href') || '', "
                "text: (e.innerText || '').trim()"
                "}))",
            )
        except Exception as e:
            print(f"  [{self.SOURCE}] filter '{team}' failed: {e}")
            return []
        finally:
            page.close()

        cards = []
        for a in anchors:
            m = _JOB_ID_RE.search(a["href"])
            if not m:
                continue
            job_id = m.group(1)
            parsed = self._parse_card_text(a["text"])
            if not parsed:
                continue
            title, location = parsed
            cards.append({
                "job_id":   job_id,
                "title":    title,
                "location": location,
            })
        return cards

    @staticmethod
    def _parse_card_text(text: str) -> tuple[str, str] | None:
        """Card inner_text usually starts: title / location / ⋅ / team / ⋅ / function.

        For most cards line 2 is the location. For a few (Data Engineer PAR,
        Data Scientist Products & Applied Research) the team comes before
        the location, so we scan each line and pick the first that looks
        like a location string. If none match, fall back to "Unknown" and
        let the base-class US-location filter default it to US.
        """
        lines = [ln.strip() for ln in text.split("\n") if ln.strip() and ln.strip() != "⋅"]
        if not lines:
            return None
        title = lines[0]
        # Search remaining lines for a location-shaped string.
        location = "Unknown"
        for ln in lines[1:6]:  # only the first few card lines, not the sidebar noise
            if _LOCATION_RE.match(ln):
                location = ln
                break
        return title, location

    def _to_job_dict(self, card):
        return {
            "title":    card["title"],
            "company":  self.COMPANY,
            "location": card["location"],
            "url":      f"{_BASE}/jobs/{card['job_id']}/",
        }


if __name__ == "__main__":
    db.init_db()
    MetaScraper().run()
