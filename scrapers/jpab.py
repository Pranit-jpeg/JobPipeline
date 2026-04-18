"""
J-PAL (Abdul Latif Jameel Poverty Action Lab) scraper — Playwright.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

CAREERS_URL = "https://www.povertyactionlab.org/careers"


class JPALScraper(BaseScraper):
    COMPANY = "J-PAL"
    SOURCE  = "jpal"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page.goto(CAREERS_URL, wait_until="networkidle", timeout=30000)

            # J-PAL careers page: job listings are typically in article/div elements
            # Try common selectors for job listing pages
            selectors_to_try = [
                "article",
                ".views-row",
                ".job-listing",
                ".career-item",
                "table tr",
            ]

            for selector in selectors_to_try:
                items = page.query_selector_all(selector)
                if len(items) > 1:
                    for item in items:
                        try:
                            anchor = item.query_selector("a[href]")
                            if not anchor:
                                continue
                            href  = anchor.get_attribute("href") or ""
                            title = anchor.inner_text().strip()
                            if not title or not href:
                                continue
                            if not href.startswith("http"):
                                href = "https://www.povertyactionlab.org" + href
                            # Location — try to find nearby text
                            text  = item.inner_text()
                            location = "Multiple Locations"
                            for loc_hint in ["Cambridge, MA", "Boston, MA", "Washington, DC",
                                             "New York", "Remote"]:
                                if loc_hint.lower() in text.lower():
                                    location = loc_hint
                                    break
                            jobs.append({"title": title, "company": self.COMPANY,
                                         "location": location, "url": href})
                        except Exception:
                            continue
                    if jobs:
                        break

            browser.close()
        return jobs


if __name__ == "__main__":
    db.init_db()
    JPALScraper().run()
