"""
Stanford University scraper — careersearch.stanford.edu (requests + BeautifulSoup).
Server-rendered: job links are <a> tags confirmed via direct HTTP fetch.
Job href pattern: /jobs/<slug>-<id> (numeric suffix, not /jobs/search/).
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
import db
from scrapers.base import BaseScraper

SEARCH_URL = "https://careersearch.stanford.edu/jobs/search/21024263"
BASE_URL   = "https://careersearch.stanford.edu"

KEYWORDS = {
    "economist", "economic", "research analyst", "data analyst",
    "policy analyst", "quantitative", "research associate",
    "research scientist", "research fellow",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Match /jobs/<slug>-<digits> only (excludes /jobs/search/... nav links)
_JOB_RE = re.compile(r"^https://careersearch\.stanford\.edu/jobs/[^/]+-\d+$")


class StanfordScraper(BaseScraper):
    COMPANY = "Stanford University"
    SOURCE  = "stanford"

    def scrape(self):
        try:
            resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [stanford] Request failed: {e}")
            return []

        soup  = BeautifulSoup(resp.text, "html.parser")
        jobs  = {}

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if not href.startswith("http"):
                href = BASE_URL + href
            if not _JOB_RE.match(href):
                continue
            if href in jobs:
                continue
            title = anchor.get_text(strip=True)
            if not title:
                continue
            if not any(kw in title.lower() for kw in KEYWORDS):
                continue
            jobs[href] = {
                "title":    title,
                "company":  self.COMPANY,
                "location": "Stanford, CA",
                "url":      href,
            }

        return list(jobs.values())


if __name__ == "__main__":
    db.init_db()
    StanfordScraper().run()
