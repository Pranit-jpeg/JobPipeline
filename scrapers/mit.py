"""
MIT scraper — PeopleClick/Kenexa careers portal (Playwright).
Searches for research and data-related roles.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

BASE_URL   = "https://careers.peopleclick.com"
SEARCH_URL = (
    "https://careers.peopleclick.com/careerscp/client_mit/external/results/searchResult.html"
    "?function=search&openNewWindow=true&searchID=&localeCode=en-us"
    "&FunctionCodeList=RSCH"  # Research functional area
)
KEYWORDS = ["research analyst", "data analyst", "economist", "policy analyst",
            "research associate", "quantitative"]


class MITScraper(BaseScraper):
    COMPANY = "MIT"
    SOURCE  = "mit"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for keyword in KEYWORDS:
                kw_url = (
                    "https://careers.peopleclick.com/careerscp/client_mit/external/results/searchResult.html"
                    f"?function=search&openNewWindow=true&searchID=&localeCode=en-us&keyword={keyword.replace(' ', '+')}"
                )
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                try:
                    page.goto(kw_url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)

                    for selector in [
                        ".searchResult",
                        "table.table tr",
                        ".jobListItem",
                        "tr[class*='job']",
                        "tr",
                    ]:
                        rows = page.query_selector_all(selector)
                        if len(rows) > 1:
                            for row in rows:
                                try:
                                    anchor = row.query_selector("a[href*='jobdetail'], a[href*='job']")
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
                                    cells    = row.query_selector_all("td")
                                    location = "Cambridge, MA"
                                    if len(cells) >= 2:
                                        for cell in cells[1:]:
                                            txt = cell.inner_text().strip()
                                            if txt and len(txt) < 60 and txt != title:
                                                location = txt
                                                break
                                    jobs[href] = {"title": title, "company": self.COMPANY,
                                                  "location": location, "url": href}
                                except Exception:
                                    continue
                            if jobs:
                                break
                except Exception:
                    pass
                finally:
                    page.close()

            browser.close()
        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    MITScraper().run()
