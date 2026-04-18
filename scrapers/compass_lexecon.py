"""
Compass Lexecon scraper — FTI Taleo portal (Playwright).
Compass Lexecon is a subsidiary of FTI Consulting.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

CAREERS_URL = "https://fticonsult.taleo.net/careersection/7.9compasslexeconcs/joblist.ftl"
BASE_URL    = "https://fticonsult.taleo.net"


class CompassLexeconScraper(BaseScraper):
    COMPANY = "Compass Lexecon"
    SOURCE  = "compass_lexecon"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                page.goto(CAREERS_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Taleo table-based layout
                for selector in [
                    "table.dataTable tr",
                    "#requisitionListInterface tr",
                    "tr.listItem",
                    "tr[class*='listrow']",
                    "tr",
                ]:
                    rows = page.query_selector_all(selector)
                    if len(rows) > 1:
                        for row in rows:
                            try:
                                anchor = row.query_selector("a[href*='jobdetail']")
                                if not anchor:
                                    anchor = row.query_selector("a[href]")
                                if not anchor:
                                    continue
                                href  = anchor.get_attribute("href") or ""
                                if not href.startswith("http"):
                                    href = BASE_URL + href
                                if href in jobs:
                                    continue
                                title = anchor.inner_text().strip()
                                if not title or len(title) < 4:
                                    continue
                                # Location usually in a sibling cell
                                cells = row.query_selector_all("td")
                                location = "Multiple Locations"
                                if len(cells) >= 3:
                                    loc_text = cells[-1].inner_text().strip()
                                    if loc_text and len(loc_text) < 60:
                                        location = loc_text
                                jobs[href] = {"title": title, "company": self.COMPANY,
                                              "location": location, "url": href}
                            except Exception:
                                continue
                        if jobs:
                            break
            except Exception as e:
                print(f"  [compass_lexecon] Error: {e}")
            finally:
                page.close()
                browser.close()

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    CompassLexeconScraper().run()
