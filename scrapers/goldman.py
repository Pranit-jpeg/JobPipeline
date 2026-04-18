"""
Goldman Sachs scraper — higher.gs.com (Phenom People, Playwright).
Single page load with scroll — no per-keyword loops to avoid timeouts.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

BASE_URL   = "https://higher.gs.com"
SEARCH_URL = "https://higher.gs.com/results?page=1&sort=RELEVANCE"

RELEVANT_KEYWORDS = {
    "economist", "economic", "research analyst", "data analyst",
    "policy analyst", "quantitative", "research associate",
    "analytics", "research scientist",
}

PHENOM_SELECTORS = [
    "[data-ph-at-id='jobs-list-item']",
    "[data-ph-id*='jobs-list-item']",
    ".jobs-list-item",
    "[class*='job-result-item']",
    "[class*='job-card']",
    "li[class*='job']",
]


class GoldmanSachsScraper(BaseScraper):
    COMPANY = "Goldman Sachs"
    SOURCE  = "goldman"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)

                # Try to find any job element — hard 10s cap per selector
                found_selector = None
                for sel in PHENOM_SELECTORS:
                    try:
                        page.wait_for_selector(sel, timeout=10000)
                        found_selector = sel
                        break
                    except Exception:
                        continue

                if not found_selector:
                    print("  [goldman] No job elements found — site may block headless browsers")
                    return []

                # Scroll to load more results (Phenom lazy-loads)
                for _ in range(3):
                    page.keyboard.press("End")
                    page.wait_for_timeout(1500)

                items = page.query_selector_all(found_selector)
                for item in items:
                    try:
                        anchor = item.query_selector("a[href]")
                        if not anchor:
                            continue
                        href = anchor.get_attribute("href") or ""
                        if not href.startswith("http"):
                            href = BASE_URL + href
                        if href in jobs:
                            continue
                        title_el = item.query_selector("h2, h3, [class*='title'], [class*='Title']")
                        title    = title_el.inner_text().strip() if title_el else anchor.inner_text().strip()
                        if not title:
                            continue
                        # Filter to relevant roles
                        if not any(kw in title.lower() for kw in RELEVANT_KEYWORDS):
                            continue
                        loc_el   = item.query_selector("[class*='location'], [class*='Location']")
                        location = loc_el.inner_text().strip() if loc_el else "Multiple Locations"
                        jobs[href] = {"title": title, "company": self.COMPANY,
                                      "location": location, "url": href}
                    except Exception:
                        continue

            except Exception as e:
                print(f"  [goldman] Error: {e}")
            finally:
                page.close()
                browser.close()

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    GoldmanSachsScraper().run()
