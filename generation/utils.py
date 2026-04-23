"""Shared helpers: JD fetch + base-resume loading."""
import os

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


def fetch_jd(url: str) -> str:
    if not url:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
        return "\n".join(lines)[:6000]
    except Exception:
        return ""


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
