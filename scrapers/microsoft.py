"""
Microsoft scraper — apply.careers.microsoft.com (SuccessFactors, Playwright).
Targets Research, Applied & Data Sciences profession category.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

SEARCH_URL = (
    "https://apply.careers.microsoft.com/careers"
    "?start=0&pid=1970393556637108&sort_by=relevance"
    "&filter_profession=research%2C%20applied%2C%20%26%20data%20sciences"
)
BASE_URL = "https://apply.careers.microsoft.com"

KEYWORDS = ["economist", "research analyst", "data analyst", "policy analyst",
            "quantitative", "research scientist", "analytics"]

# Microsoft careers uses "pcsx-jobcard" component names (from page config)
MS_SELECTORS = [
    "[class*='pcsx-jobcard']",
    ".pcsx-jobcard",
    "[class*='job-result']",
    "[class*='ms-List-cell']",
    "[class*='JobCard']",
    "li[class*='job']",
    "article",
]


class MicrosoftScraper(BaseScraper):
    COMPANY = "Microsoft"
    SOURCE  = "microsoft"

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
                # Wait for job cards to hydrate
                for sel in MS_SELECTORS:
                    try:
                        page.wait_for_selector(sel, timeout=8000)
                        break
                    except Exception:
                        continue

                for selector in MS_SELECTORS:
                    items = page.query_selector_all(selector)
                    if not items:
                        continue
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
                            loc_el   = item.query_selector("[class*='location'], [class*='Location']")
                            location = loc_el.inner_text().strip() if loc_el else "Multiple Locations"
                            jobs[href] = {"title": title, "company": self.COMPANY,
                                          "location": location, "url": href}
                        except Exception:
                            continue
                    if jobs:
                        break
            except Exception as e:
                print(f"  [microsoft] Error: {e}")
            finally:
                page.close()
                browser.close()

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    MicrosoftScraper().run()
