"""Shared helpers: JD fetch + base-resume loading."""
import logging
import os
import re

import requests
from bs4 import BeautifulSoup

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG_DIR)
RESUME_DIR = os.path.join(_ROOT, "resumes")
GENERATED_DIR = os.path.join(_ROOT, "generated")

RESUME_FILES = {
    "EconPolicy":        "econ_policy.txt",
    "FinanceConsulting": "finance_consulting.txt",
    "DataAnalyst":       "data_analyst.txt",
    "ResearchAnalyst":   "research_analyst.txt",
}

_log = logging.getLogger(__name__)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

# Threshold under which we assume the page was JS-rendered and the static fetch
# only returned the empty shell (Workday, Greenhouse, Lever, etc.).
_MIN_JD_CHARS = 800


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
    return "\n".join(lines)[:6000]


def _fetch_jd_static(url: str) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        return _extract_text(resp.text)
    except Exception as e:
        _log.info("static JD fetch failed for %s: %s", url, e)
        return ""


def _fetch_jd_playwright(url: str) -> str:
    """Browser fallback for JS-rendered career pages. Slower (~5-10s) but reliable.

    Uses networkidle to adapt to site speed — most ATS pages settle within 3s
    of network silence, but slow SPAs (csod.com, some Workday tenants) need
    longer XHR cycles. The hard timeout caps total wait at ~25s.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=_UA)
            page = ctx.new_page()
            try:
                # networkidle = wait for 500ms of no network activity. This
                # captures async XHR-loaded content (React SPAs, Workday CXS).
                # Fall back to domcontentloaded if networkidle times out.
                try:
                    page.goto(url, wait_until="networkidle", timeout=20000)
                except Exception as e:
                    _log.info("networkidle wait timed out for %s, falling back to domcontentloaded: %s", url, e)
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                # Belt-and-suspenders: extra fixed wait for any final renders.
                page.wait_for_timeout(2500)
                html = page.content()
            finally:
                browser.close()
        return _extract_text(html)
    except Exception as e:
        _log.warning("playwright JD fetch failed for %s: %s", url, e)
        return ""


def fetch_jd(url: str) -> str:
    """Best-effort JD fetch. Tries static HTTP first; falls back to a headless
    browser if the static fetch returned suspiciously little content (indicating
    a JS-rendered page).
    """
    if not url:
        return ""
    static = _fetch_jd_static(url)
    if len(static) >= _MIN_JD_CHARS:
        return static
    _log.info("static JD fetch returned %d chars (< %d) — falling back to playwright",
              len(static), _MIN_JD_CHARS)
    dynamic = _fetch_jd_playwright(url)
    # Take whichever is longer so we don't downgrade if Playwright fails
    return dynamic if len(dynamic) > len(static) else static


def load_resume(resume_version: str) -> str | None:
    filename = RESUME_FILES.get(resume_version)
    if not filename:
        return None
    path = os.path.join(RESUME_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def slugify(text: str, max_len: int = 40) -> str:
    """Filesystem-safe slug."""
    keep = "".join(c if c.isalnum() or c in "-_ " else "" for c in text).strip()
    return keep.replace(" ", "_")[:max_len] or "untitled"


# Patterns we never want to render as a company-address line. These are
# scraper-leakage strings (the listing page literally said "4 Locations
# Available") not real cities.
_JUNK_LOCATION_RE = re.compile(
    r"^("
    r"\d+\s+locations?\s+available"        # "4 Locations Available"
    r"|multiple\s+locations?"               # "Multiple Locations"
    r"|various\s+locations?"
    r"|locations?\s+available"
    r"|see\s+(job|posting)"
    r"|n/?a"
    r")\s*$",
    re.IGNORECASE,
)


def is_junk_location(location: str) -> bool:
    """True if `location` is a scraper-output placeholder, not a real address."""
    if not location:
        return True
    return bool(_JUNK_LOCATION_RE.match(location.strip()))


def build_company_address_line(location: str, indent: str = "   ") -> str:
    """Return the optional second line of a cover-letter address block.

    Empty string when the location is missing or junk — the caller can
    concatenate this directly after the company name without producing a
    blank line in the rendered letter.
    """
    if is_junk_location(location):
        return ""
    return f"\n{indent}{location.strip()}"
