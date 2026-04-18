"""
Predoc.org scraper — aggregated pre-doctoral & RA listings (Playwright).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

OPPORTUNITIES_URL = "https://www.predoc.org/opportunities"

KEYWORDS = {
    "research assistant", "research analyst", "research associate",
    "pre-doctoral", "predoctoral", "pre doctoral",
    "data analyst", "policy analyst", "economist",
}


class PredocScraper(BaseScraper):
    COMPANY = "Predoc.org"
    SOURCE  = "predoc"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page.goto(OPPORTUNITIES_URL, wait_until="networkidle", timeout=45000)

            # Scroll to load all listings
            for _ in range(5):
                page.keyboard.press("End")
                page.wait_for_timeout(1000)

            # Predoc.org uses card-based listings
            selectors_to_try = [
                ".opportunity-card",
                ".job-card",
                "[class*='opportunity']",
                "[class*='listing']",
                "article",
                ".card",
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
                            title = item.query_selector("h2, h3, h4, .title, [class*='title']")
                            title_text = title.inner_text().strip() if title else anchor.inner_text().strip()
                            if not title_text or not href:
                                continue
                            # Filter to relevant keywords
                            if not any(kw in title_text.lower() for kw in KEYWORDS):
                                continue
                            if not href.startswith("http"):
                                href = "https://www.predoc.org" + href
                            # Org / location
                            org_el = item.query_selector("[class*='org'], [class*='institution'], [class*='employer']")
                            company = org_el.inner_text().strip() if org_el else self.COMPANY
                            loc_el  = item.query_selector("[class*='location'], [class*='loc']")
                            location = loc_el.inner_text().strip() if loc_el else "Multiple Locations"
                            jobs.append({"title": title_text, "company": company or self.COMPANY,
                                         "location": location, "url": href})
                        except Exception:
                            continue
                    if jobs:
                        break

            browser.close()
        return jobs


if __name__ == "__main__":
    db.init_db()
    PredocScraper().run()
