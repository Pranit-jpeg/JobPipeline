"""
Brookings Institution scraper — uses Playwright to scrape iCIMS portal.
Brookings has a small number of openings; we fetch all and save them.
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

SEARCH_URL = "https://careers-brookings.icims.com/jobs/search?ss=1"
BASE_URL = "https://careers-brookings.icims.com"


def _parse_location(raw):
    """Convert iCIMS format 'US-DC-Washington' → 'Washington, DC'."""
    raw = raw.strip()
    parts = raw.split("-")
    if len(parts) >= 3 and len(parts[0]) == 2:  # starts with country code
        state = parts[1]
        city = " ".join(parts[2:])
        return f"{city}, {state}"
    return raw


class BrookingsScraper(BaseScraper):
    COMPANY = "Brookings Institution"
    SOURCE = "brookings"

    def scrape(self):
        from playwright.sync_api import sync_playwright

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)

            # iCIMS loads content in a nested iframe
            frames = page.frames
            inner = frames[1] if len(frames) > 1 else frames[0]

            items = inner.query_selector_all("li.iCIMS_JobCardItem")
            for item in items:
                try:
                    anchor = item.query_selector("a.iCIMS_Anchor")
                    if not anchor:
                        continue
                    href = anchor.get_attribute("href") or ""
                    # Strip iframe param and get clean URL
                    url = re.sub(r'\?.*', '', href)
                    if not url.startswith("http"):
                        url = BASE_URL + url

                    title_el = item.query_selector("h3")
                    title = title_el.inner_text().strip() if title_el else anchor.get_attribute("title") or ""
                    # Clean title: iCIMS sometimes wraps "Job Title\nActual Title"
                    title_lines = [ln.strip() for ln in title.splitlines() if ln.strip()]
                    title = title_lines[-1] if title_lines else title

                    # Location is in a <span> containing the US-STATE-CITY pattern
                    loc_spans = item.query_selector_all("span")
                    location = "Washington, DC"  # Brookings default
                    for span in loc_spans:
                        txt = span.inner_text().strip()
                        if re.match(r'^[A-Z]{2}-[A-Z]', txt):
                            location = _parse_location(txt)
                            break

                    if title and url:
                        jobs.append({"title": title, "company": self.COMPANY,
                                     "location": location, "url": url})
                except Exception:
                    continue

            browser.close()
        return jobs


if __name__ == "__main__":
    db.init_db()
    BrookingsScraper().run()
