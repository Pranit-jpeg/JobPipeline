"""
Massachusetts state jobs scraper — Playwright-based scraper for the
Commonwealth's Taleo career portal (massanf.taleo.net).
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

SEARCH_URL = "https://massanf.taleo.net/careersection/ex/jobsearch.ftl?lang=en"
BASE_URL   = "https://massanf.taleo.net"

KEYWORDS = [
    "economist",
    "policy analyst",
    "research analyst",
    "data analyst",
    "quantitative",
]

# Maps full state name to abbreviation for location formatting
_STATE_ABBR = {
    "Massachusetts": "MA", "Connecticut": "CT", "Rhode Island": "RI",
    "New Hampshire": "NH", "Vermont": "VT", "Maine": "ME",
}


def _clean_location(raw):
    """Convert 'Massachusetts-Boston' → 'Boston, MA'."""
    if "-" in raw:
        parts = raw.split("-", 1)
        state_name = parts[0].strip()
        city = parts[1].strip()
        abbr = _STATE_ABBR.get(state_name, state_name)
        return f"{city}, {abbr}"
    return raw.strip() or "Massachusetts"


def _parse_row(row, base_url):
    """Extract job dict from a <li id='jobXXX'> element."""
    link = row.query_selector("a[href*='jobdetail']")
    if not link:
        return None

    href  = link.get_attribute("href") or ""
    url   = href if href.startswith("http") else base_url + href
    title = link.get_attribute("title") or link.inner_text().strip()
    if not title or not url:
        return None

    # Location lives in the div whose first span says "Work Locations"
    location = "Massachusetts"
    for div in row.query_selector_all("div"):
        spans = div.query_selector_all("span")
        texts = [s.inner_text().strip() for s in spans]
        if texts and texts[0] == "Work Locations":
            # Last non-empty span has the value
            values = [t for t in texts[1:] if t and t not in (":", " ")]
            if values:
                location = _clean_location(values[-1])
            break

    return {"title": title, "company": "Commonwealth of Massachusetts",
            "location": location, "url": url}


class MassGovScraper(BaseScraper):
    COMPANY = "Commonwealth of Massachusetts"
    SOURCE  = "mass_gov"

    def _scrape_keyword(self, page, keyword):
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)

        kw_input = page.query_selector('input[id="KEYWORD"]')
        if not kw_input:
            print(f"  [mass_gov] Search input not found for '{keyword}'")
            return []
        kw_input.fill(keyword)

        search_btn = page.query_selector('input[id="search"]')
        if not search_btn:
            print(f"  [mass_gov] Search button not found for '{keyword}'")
            return []
        search_btn.click()
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(1)

        jobs = []
        while True:
            rows = page.query_selector_all("li[id^='job']")
            for row in rows:
                job = _parse_row(row, BASE_URL)
                if job:
                    jobs.append(job)

            # Pagination — Taleo uses an <a> with class containing "next"
            next_btn = page.query_selector("a.next-link:not(.disabled), a[title='Next Page']")
            if not next_btn:
                break
            try:
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(0.5)
            except Exception:
                break

        return jobs

    def scrape(self):
        from playwright.sync_api import sync_playwright

        all_jobs = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            for keyword in KEYWORDS:
                try:
                    found = self._scrape_keyword(page, keyword)
                    for job in found:
                        if job["url"] not in all_jobs:
                            all_jobs[job["url"]] = job
                except Exception as e:
                    print(f"  [mass_gov] Error scraping '{keyword}': {e}")
                time.sleep(1)
            browser.close()

        return list(all_jobs.values())


if __name__ == "__main__":
    db.init_db()
    MassGovScraper().run()
