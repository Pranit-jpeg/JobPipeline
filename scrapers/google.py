"""
Google careers scraper — Playwright-based, parses the embedded ds:1 script data.
Jobs are rendered client-side; this scraper waits for JS execution then reads
the AF_initDataCallback data block for job IDs, titles, and URLs.
"""

import sys, os, re, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.base import BaseScraper

SEARCH_TPL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
    "?q={keyword}&location=United+States"
)

KEYWORDS = ["economist", "policy analyst", "research analyst", "data analyst"]

def _is_relevant(title):
    return bool(title)  # entry-level filter handled centrally in BaseScraper.run()


def _extract_jobs(script_content):
    """Pull [job_id, title, url] triples from the embedded AF_initDataCallback."""
    jobs = {}
    entries = re.findall(
        r'\["(\d{15,20})","([^"]+)","(https://[^"]*?signin[^"]*?)"',
        script_content,
    )
    for job_id, title, raw_url in entries:
        url = (raw_url
               .replace("\\u003d", "=")
               .replace("\\u0026", "&")
               .replace("\\u003c", "<")
               .replace("\\u003e", ">"))
        if job_id not in jobs and title:
            jobs[job_id] = {"id": job_id, "title": title, "url": url}
    return jobs


def _extract_locations(page_text, titles):
    """
    Best-effort: the rendered page text has a predictable structure per job:
      {title}\\nGoogle\\nplace\\n{location}\\n...
    """
    locations = {}
    for title in titles:
        idx = page_text.find(title)
        if idx < 0:
            continue
        snippet = page_text[idx: idx + 400]
        lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            if line == "place" and i + 1 < len(lines):
                loc = lines[i + 1].split(";")[0].strip()
                if len(loc) > 4 and "bar_chart" not in loc:
                    locations[title] = loc
                break
    return locations


class GoogleScraper(BaseScraper):
    COMPANY = "Google"
    SOURCE  = "google"

    def _scrape_keyword(self, page, keyword):
        url = SEARCH_TPL.format(keyword=keyword.replace(" ", "+"))
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(6)

        script_content = page.evaluate('''() => {
            const scripts = [...document.querySelectorAll("script")];
            const ds1 = scripts.find(s => s.className === "ds:1");
            return ds1 ? ds1.textContent : "";
        }''')

        if not script_content:
            return {}

        jobs = _extract_jobs(script_content)
        page_text = page.evaluate('() => document.body.innerText')
        locations = _extract_locations(page_text, [j["title"] for j in jobs.values()])

        for job in jobs.values():
            job["location"] = locations.get(job["title"], "United States")

        return jobs

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
                    found = self._scrape_keyword(page, keyword)
                    for job_id, job in found.items():
                        if job_id not in all_jobs and _is_relevant(job["title"]):
                            all_jobs[job_id] = job
                except Exception as e:
                    print(f"  [google] Error for '{keyword}': {e}")
                time.sleep(1)
            browser.close()

        return [
            {"title": j["title"], "company": "Google",
             "location": j["location"], "url": j["url"]}
            for j in all_jobs.values()
        ]


if __name__ == "__main__":
    db.init_db()
    GoogleScraper().run()
