"""
NERA Economic Consulting scraper — careers.marsh.com (Phenom People, Playwright).
NERA is a subsidiary of Marsh McLennan; jobs appear on the Marsh careers portal.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

SEARCH_URL = "https://careers.marsh.com/global/en/nera-search"
BASE_URL   = "https://careers.marsh.com"


class NERAScraper(BaseScraper):
    COMPANY = "NERA Economic Consulting"
    SOURCE  = "nera"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                page.goto(SEARCH_URL, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(3000)

                # Phenom People selectors
                for selector in [
                    "[data-ph-id*='job']",
                    "[class*='job-card']",
                    "[class*='JobCard']",
                    "[class*='job-list-item']",
                    "li[class*='job']",
                    "article",
                ]:
                    items = page.query_selector_all(selector)
                    if len(items) > 0:
                        for item in items:
                            try:
                                anchor = item.query_selector("a[href]")
                                if not anchor:
                                    continue
                                href  = anchor.get_attribute("href") or ""
                                if not href.startswith("http"):
                                    href = BASE_URL + href
                                if href in jobs:
                                    continue
                                title_el = item.query_selector("h2, h3, [class*='title'], [class*='Title']")
                                title    = title_el.inner_text().strip() if title_el else anchor.inner_text().strip()
                                if not title:
                                    continue
                                loc_el   = item.query_selector("[class*='location'], [class*='Location']")
                                location = loc_el.inner_text().strip() if loc_el else "Multiple Locations"
                                jobs[href] = {"title": title, "company": self.COMPANY,
                                              "location": location, "url": href}
                            except Exception:
                                continue
                        if jobs:
                            break
            except Exception as e:
                print(f"  [nera] Error: {e}")
            finally:
                page.close()
                browser.close()

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    NERAScraper().run()
