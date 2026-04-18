"""
Moody's Corporation careers scraper — Playwright-based scraper for
careers.moodys.com (Paradox AI-powered career site).
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

JOBS_URL = "https://careers.moodys.com/jobs"
BASE_URL = "https://careers.moodys.com"

KEYWORDS = ["economist", "research analyst", "data analyst",
            "policy analyst", "quantitative"]


class MoodyScraper(BaseScraper):
    COMPANY = "Moody's Corporation"
    SOURCE  = "moodys"

    def _parse_page(self, page):
        jobs = []
        for card in page.query_selector_all("li.results-list__item"):
            try:
                link = card.query_selector("a.results-list__item-title--link")
                if not link:
                    continue
                href  = link.get_attribute("href") or ""
                url   = href if href.startswith("http") else BASE_URL + href
                title = link.inner_text().strip()
                if not title:
                    continue
                loc_el   = card.query_selector("span.results-list__item-street--label")
                location = loc_el.inner_text().strip() if loc_el else "Unknown"
                jobs.append({"title": title, "company": self.COMPANY,
                             "location": location, "url": url})
            except Exception:
                continue
        return jobs

    def _scrape_keyword(self, page, keyword):
        page.goto(JOBS_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        inp = (page.query_selector('input[id*="keyword-search-input"]') or
               page.query_selector('input[placeholder*="search"]'))
        if not inp:
            print(f"  [moodys] Search input not found for '{keyword}'")
            return []

        inp.fill(keyword)
        inp.press("Enter")
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(2)

        all_jobs = []
        while True:
            all_jobs.extend(self._parse_page(page))

            next_btn = (
                page.query_selector("button[aria-label*='Next Page']") or
                page.query_selector("a[aria-label*='Next Page']") or
                page.query_selector("[class*='pagination'][class*='next']:not([disabled])")
            )
            if not next_btn:
                break
            try:
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)
            except Exception:
                break

        return all_jobs

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
                    for job in self._scrape_keyword(page, keyword):
                        if job["url"] not in all_jobs:
                            all_jobs[job["url"]] = job
                except Exception as e:
                    print(f"  [moodys] Error scraping '{keyword}': {e}")
                time.sleep(1)
            browser.close()

        return list(all_jobs.values())


if __name__ == "__main__":
    db.init_db()
    MoodyScraper().run()
