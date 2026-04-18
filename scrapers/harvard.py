"""
Harvard University scraper — Atom feed from academicpositions.harvard.edu.
No Playwright needed — direct XML feed.
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import xml.etree.ElementTree as ET
import db
from scrapers.base import BaseScraper

ATOM_URL  = "https://academicpositions.harvard.edu/postings/all_jobs.atom"
ATOM_NS   = "http://www.w3.org/2005/Atom"

KEYWORDS = {
    "economist", "economic", "research analyst", "research associate",
    "data analyst", "policy analyst", "quantitative", "research scientist",
    "predoctoral", "pre-doctoral", "research fellow",
}


class HarvardScraper(BaseScraper):
    COMPANY = "Harvard University"
    SOURCE  = "harvard"
    IGNORE_FRESHNESS = True  # academic postings stay live for weeks/months

    def scrape(self):
        resp = requests.get(ATOM_URL, timeout=20)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        jobs = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            title_el = entry.find(f"{{{ATOM_NS}}}title")
            title    = title_el.text.strip() if title_el is not None else ""

            # Filter to research/econ relevant roles
            if not any(kw in title.lower() for kw in KEYWORDS):
                continue

            link_el = entry.find(f"{{{ATOM_NS}}}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{{{ATOM_NS}}}link")
            url = link_el.get("href", "") if link_el is not None else ""

            # Department from <author><name>
            author_el = entry.find(f"{{{ATOM_NS}}}author/{{{ATOM_NS}}}name")
            department = author_el.text.strip() if author_el is not None else ""

            # Location: scan content HTML for city/state clues
            content_el = entry.find(f"{{{ATOM_NS}}}content")
            content    = content_el.text or "" if content_el is not None else ""
            location   = "Cambridge, MA"   # Harvard default
            for loc in ["Boston, MA", "Washington, DC", "New York", "Remote"]:
                if loc.lower() in content.lower():
                    location = loc
                    break

            # Date posted
            pub_el     = entry.find(f"{{{ATOM_NS}}}published")
            date_posted = pub_el.text[:10] if pub_el is not None else None

            if title and url:
                jobs.append({
                    "title":       title,
                    "company":     f"Harvard — {department}" if department else self.COMPANY,
                    "location":    location,
                    "url":         url,
                    "date_posted": date_posted,
                })

        return jobs


if __name__ == "__main__":
    db.init_db()
    HarvardScraper().run()
