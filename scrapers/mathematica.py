"""
Mathematica scraper — uses Playwright to scrape Cornerstone OnDemand (CSOD) portal.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

HOME_URL = "https://mathematica.csod.com/ux/ats/careersite/4/home?c=mathematica"
BASE_URL = "https://mathematica.csod.com"


class MathematicaScraper(BaseScraper):
    COMPANY = "Mathematica"
    SOURCE = "mathematica"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page.goto(HOME_URL, wait_until="networkidle", timeout=30000)

            anchors = page.query_selector_all("a[data-tag='displayJobTitle']")
            for anchor in anchors:
                try:
                    href = anchor.get_attribute("href") or ""
                    url = BASE_URL + href if href.startswith("/") else href

                    title_el = anchor.query_selector("p")
                    title = title_el.inner_text().strip() if title_el else anchor.inner_text().strip()

                    # Location is the next <p data-tag="displayJobLocation"> sibling
                    loc_el = page.query_selector(
                        f"a[href='{href}'] + p[data-tag='displayJobLocation'], "
                        f"a[href='{href}'] ~ p[data-tag='displayJobLocation']"
                    )
                    if not loc_el:
                        # fallback: look inside the same parent container
                        parent = anchor.evaluate_handle("el => el.closest('div')")
                        loc_el = parent.query_selector("p[data-tag='displayJobLocation']") if parent else None

                    location = loc_el.inner_text().strip() if loc_el else "Multiple Locations"

                    if title and url:
                        jobs.append({"title": title, "company": self.COMPANY,
                                     "location": location, "url": url})
                except Exception:
                    continue

            browser.close()
        return jobs


if __name__ == "__main__":
    db.init_db()
    MathematicaScraper().run()
