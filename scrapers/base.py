import sys
import os
import re
import time
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from h1b_sponsors import get_h1b_status

# ── Entry-level filter ────────────────────────────────────────────────────────

MAX_AGE_HOURS = 36

# Substrings that always disqualify a title as too senior, regardless of
# company leveling conventions. Titles are padded with spaces in the check
# below so " lead " won't match "leadership".
_EXCLUDE_TERMS = [
    "senior", " sr.", "(sr)", " sr ",          # "Sr Researcher" with no period (Uber convention)
    "staff ",                                    # "Staff Engineer/Scientist" = senior IC at Meta/Uber/Google
    "lead ",
    "principal",
    "director",
    " manager",
    "vice president", " vp ", " vp,",
    "chief ",
    "head of",
    "managing",
    "executive director", "executive vice",
    "associate director", "associate vp", "associate vice",
]

# Roman-numeral level suffixes. At consulting and research firms ("Researcher
# II", "Director II"), these indicate mid-senior or above. At big-tech
# companies (Uber, Amazon, Google when active), "Engineer II" / "Data
# Scientist II" is L3-L4 — mid-level, MS-new-grad eligible. So this list is
# applied opt-in via the BaseScraper.STRICT_LEVEL_FILTER class attribute.
_ROMAN_LEVEL_TERMS = [" ii ", " iii ", " iv "]


def is_entry_level(title: str, strict_levels: bool = True) -> bool:
    """Return True if the title looks like an entry-level or early-career role.

    `strict_levels=False` is intended for big-tech scrapers where the
    Roman-numeral convention shifts: "II/III" titles at Uber/Amazon are
    mid-level, not senior.
    """
    t = f" {title.lower()} "
    if any(term in t for term in _EXCLUDE_TERMS):
        return False
    if strict_levels and any(term in t for term in _ROMAN_LEVEL_TERMS):
        return False
    return True


# Substrings that mark a title as topically relevant to Pranit's target roles.
# Only titles containing at least one of these make it into the pipeline —
# stops the LLM from wasting credits scoring obviously off-topic postings
# (e.g. Amazon Supply Chain Ops Analyst, Google Trust & Safety Specialist).
_INCLUDE_TERMS = [
    "economist", "economic",     # covers "Economic Analyst", "Economics Research"
    "analyst", "analytics",
    "research",                   # covers Research Associate / Assistant / Fellow / Scientist
    "policy",
    "data ",                      # trailing space avoids matching "metadata"
    " data,",
    "quantitative", "quant ",
    "statistician",
    "consultant", "consulting",
    "fellow",                     # research fellow, policy fellow
    "econ ", " econ,",            # short form when full word absent
    "associate",                  # research associate, consulting associate
    "intern",                     # many policy/research internships still fit
    "scientist",                  # applied scientist, data scientist, research scientist
    "predoctoral", "pre-doctoral", "doctoral",
]


def matches_target_role(title: str) -> bool:
    """Return True if the title contains at least one target-role keyword."""
    t = f" {title.lower()} "
    return any(term in t for term in _INCLUDE_TERMS)


# ── US-location filter ────────────────────────────────────────────────────────

_US_STATE_ABBRS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","PR",
}

_US_STATE_NAMES = {
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut",
    "delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa",
    "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
    "minnesota","mississippi","missouri","montana","nebraska","nevada",
    "new hampshire","new jersey","new mexico","new york","north carolina",
    "north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island",
    "south carolina","south dakota","tennessee","texas","utah","vermont",
    "virginia","washington","west virginia","wisconsin","wyoming",
    "district of columbia","puerto rico",
}

_US_SIGNALS = {
    "united states", "usa", "u.s.a.", "u.s.", " us ",
    "remote - us", "remote, us", "remote us", "us remote", "us-remote",
    "remote (us)", "remote (usa)", "nationwide",
}

# Non-US signals: country names and prominent cities strongly associated with
# non-US offices. Anything here (without a US state/abbr also present) rejects.
_NON_US_COUNTRIES = {
    "united kingdom","uk","u.k.","england","scotland","wales","northern ireland",
    "ireland","france","germany","spain","italy","netherlands","belgium",
    "switzerland","sweden","norway","denmark","finland","poland","portugal",
    "austria","luxembourg","czech","greece","romania","hungary",
    "canada","mexico","brazil","argentina","chile","colombia",
    "india","china","japan","singapore","hong kong","south korea","korea",
    "taiwan","thailand","vietnam","malaysia","indonesia","philippines",
    "australia","new zealand",
    "uae","united arab emirates","saudi arabia","israel","qatar","egypt",
    "south africa","kenya","nigeria","turkey","russia",
}

_NON_US_CITIES = {
    "london","manchester","edinburgh","dublin","paris","berlin","munich",
    "frankfurt","amsterdam","rotterdam","brussels","madrid","barcelona","rome",
    "milan","zurich","geneva","stockholm","oslo","copenhagen","helsinki",
    "warsaw","lisbon","vienna","prague","athens","budapest",
    "toronto","montreal","vancouver","ottawa","calgary",
    "mexico city","sao paulo","buenos aires","santiago","bogota",
    "mumbai","bangalore","bengaluru","delhi","hyderabad","chennai","pune",
    "gurgaon","gurugram","noida","kolkata",
    "beijing","shanghai","shenzhen","guangzhou",
    "tokyo","osaka","seoul","taipei","bangkok","kuala lumpur","jakarta",
    "manila","ho chi minh","hanoi",
    "sydney","melbourne","brisbane","auckland","wellington",
    "dubai","abu dhabi","riyadh","doha","tel aviv","istanbul",
}


_UK_SIGNALS = {"united kingdom", "uk", "u.k.", "england", "scotland", "wales",
               "northern ireland", "britain", "great britain"}
_UK_CITIES  = {"london", "manchester", "edinburgh", "birmingham", "leeds",
               "bristol", "glasgow", "liverpool", "sheffield", "cardiff",
               "belfast", "reading"}

_UAE_SIGNALS = {"uae", "u.a.e.", "united arab emirates"}
_UAE_CITIES  = {"dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah",
                "al ain"}

_NL_SIGNALS = {"netherlands", "holland", "the netherlands"}
_NL_CITIES  = {"amsterdam", "rotterdam", "the hague", "den haag", "utrecht",
               "eindhoven", "groningen", "tilburg"}

_IN_SIGNALS = {"india"}
_IN_CITIES  = {"mumbai", "bangalore", "bengaluru", "new delhi", "delhi",
               "hyderabad", "chennai", "pune", "gurgaon", "gurugram",
               "noida", "kolkata", "ahmedabad", "jaipur", "chandigarh",
               "indore", "coimbatore"}


def _has_signal(low, tokens, signals, cities):
    if any(s in low for s in signals):
        return True
    for t in tokens:
        if t in cities:
            return True
        for c in cities:
            if c in t:
                return True
    return False


def classify_location(location: str):
    """
    Return a country code for allowed regions, or None to reject.
    Allowed: 'US' (primary), 'UK', 'UAE', 'NL', 'IN' (secondary).
    Ambiguous strings (empty, "Remote", "Multiple Locations") default to 'US'.
    """
    if not location:
        return "US"

    raw = location.strip()
    if not raw:
        return "US"

    low = raw.lower()

    ambiguous = {"unknown", "multiple locations", "various", "remote", "flexible"}
    if low in ambiguous:
        return "US"

    tokens = [t.strip() for t in re.split(r"[,/()\-|;]", low) if t.strip()]

    # 1. US signals take priority (state abbrs are unambiguous with uppercase tokens)
    if any(sig in low for sig in _US_SIGNALS):
        return "US"
    for tok in tokens:
        if tok in _US_STATE_NAMES:
            return "US"
    for tok in re.split(r"[,/()\-|;\s]+", raw):
        if tok in _US_STATE_ABBRS:
            return "US"

    # 2. Secondary allowed countries
    if _has_signal(low, tokens, _UAE_SIGNALS, _UAE_CITIES):
        return "UAE"
    if _has_signal(low, tokens, _NL_SIGNALS, _NL_CITIES):
        return "NL"
    if _has_signal(low, tokens, _IN_SIGNALS, _IN_CITIES):
        return "IN"
    if _has_signal(low, tokens, _UK_SIGNALS, _UK_CITIES):
        return "UK"

    # 3. Explicit non-allowed country/city → reject
    if any(country in low for country in _NON_US_COUNTRIES):
        return None
    for tok in tokens:
        if tok in _NON_US_CITIES:
            return None
        for city in _NON_US_CITIES:
            if city in tok:
                return None

    # 4. Nothing conclusive — default to US.
    return "US"


def _parse_date_posted(s):
    """Parse a date/datetime string to a UTC-aware datetime, or None on failure."""
    if not s:
        return None
    s = str(s).strip()
    # Strip common timezone suffixes before parsing
    s = re.sub(r'(Z|[+-]\d{2}:?\d{2})$', '', s)
    s = s[:26]  # cap at microsecond precision
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_fresh(date_posted_str) -> bool:
    """Return True if the posting is within MAX_AGE_HOURS, or if no date is known."""
    if not date_posted_str:
        return True
    dt = _parse_date_posted(date_posted_str)
    if dt is None:
        return True
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    return age_hours <= MAX_AGE_HOURS


# ── HTTP helpers ──────────────────────────────────────────────────────────────

_WD_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

DEFAULT_KEYWORDS = [
    "economist",
    "research analyst",
    "data analyst",
    "policy analyst",
    "quantitative analyst",
    "research associate",
]


class BaseScraper:
    COMPANY = "Unknown"
    SOURCE = "unknown"
    IGNORE_FRESHNESS = False  # set True for feeds where postings are intentionally weeks old
    # Set False on big-tech scrapers (Uber, Amazon, Google) where "Engineer II"
    # is mid-level. Default True keeps the conservative filter for consulting,
    # research, and policy employers.
    STRICT_LEVEL_FILTER = True

    def scrape(self):
        """Return a list of job dicts with keys: title, company, location, url, salary (optional)."""
        raise NotImplementedError

    def run(self):
        """Scrape jobs and save new ones to the database. Prints a summary."""
        print(f"[{self.SOURCE}] Scraping {self.COMPANY}...")
        try:
            jobs = self.scrape()
        except Exception as e:
            print(f"[{self.SOURCE}] ERROR: {e}")
            return 0

        skipped_senior      = 0
        skipped_offtopic    = 0
        skipped_stale       = 0
        skipped_non_allowed = 0
        new_count           = 0

        for job in jobs:
            title = job["title"]

            if not is_entry_level(title, strict_levels=self.STRICT_LEVEL_FILTER):
                skipped_senior += 1
                continue

            if not matches_target_role(title):
                skipped_offtopic += 1
                continue

            if classify_location(job.get("location", "")) is None:
                skipped_non_allowed += 1
                continue

            date_posted = job.get("date_posted")
            if not self.IGNORE_FRESHNESS and not is_fresh(date_posted):
                skipped_stale += 1
                continue

            company    = job.get("company", self.COMPANY)
            h1b_status = get_h1b_status(company)

            added = db.add_job(
                title=title,
                company=company,
                location=job["location"],
                url=job["url"],
                source=self.SOURCE,
                salary=job.get("salary"),
                date_posted=date_posted,
                h1b_status=h1b_status,
            )
            if added:
                new_count += 1

        print(
            f"[{self.SOURCE}] Done — {new_count} new job(s) added "
            f"({len(jobs)} found, {skipped_senior} senior, "
            f"{skipped_offtopic} off-topic, {skipped_non_allowed} non-allowed, "
            f"{skipped_stale} stale)."
        )
        return new_count


class WorkdayScraper(BaseScraper):
    """Base class for any org that uses Workday (myworkdayjobs.com)."""
    WD_HOST = ""    # e.g. "rb.wd5.myworkdayjobs.com"
    WD_TENANT = ""  # e.g. "rb"
    WD_SITE = ""    # e.g. "FRS"
    KEYWORDS = DEFAULT_KEYWORDS

    def _api_url(self):
        return f"https://{self.WD_HOST}/wday/cxs/{self.WD_TENANT}/{self.WD_SITE}/jobs"

    def _job_base_url(self):
        return f"https://{self.WD_HOST}/{self.WD_SITE}"

    def _fetch_keyword(self, keyword):
        url = self._api_url()
        headers = {**_WD_HEADERS, "Referer": self._job_base_url()}
        jobs = {}
        offset = 0
        limit = 20
        while True:
            payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": keyword}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{self.SOURCE}] Request failed for '{keyword}': {e}")
                break
            data = resp.json()
            postings = data.get("jobPostings", [])
            if not postings:
                break
            for job in postings:
                path = job.get("externalPath", "")
                if path and path not in jobs:
                    jobs[path] = job
            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break
            time.sleep(0.4)
        return jobs

    def _build_job(self, path, job):
        return {
            "title":       job.get("title", "").strip(),
            "company":     self.COMPANY,
            "location":    job.get("locationsText", "Unknown").strip(),
            "url":         self._job_base_url() + path,
            "date_posted": job.get("postedOn"),  # Workday returns ISO date string
        }

    def scrape(self):
        all_jobs = {}
        for keyword in self.KEYWORDS:
            found = self._fetch_keyword(keyword)
            all_jobs.update(found)
            time.sleep(0.6)
        return [self._build_job(path, job) for path, job in all_jobs.items()]
