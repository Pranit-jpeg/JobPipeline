"""
Run all scrapers in sequence and print a summary.
Usage: python -m scrapers.run_all
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

# ── Active scrapers: corporate employers that sponsor H-1B ────────────────────
# Dropped (files kept for reference, not imported):
#   • Government (visa dead-ends, require US citizenship):
#     usajobs, treasury, usda_ers, mass_gov, nyc_gov
#   • Academic (not corporate per current career focus):
#     predoc, harvard, mit, stanford, uchicago, bfi, jpab
#   • Blocks headless browsers:
#     goldman, microsoft

from scrapers.fed_boston import FedReserveScraper   # quasi-private, occasional sponsorship
from scrapers.urban_institute import UrbanInstituteScraper
from scrapers.rand import RandScraper
from scrapers.brookings import BrookingsScraper
from scrapers.mathematica import MathematicaScraper
from scrapers.abt import AbtScraper
from scrapers.amazon import AmazonScraper
from scrapers.google import GoogleScraper
from scrapers.jpmorgan import JPMorganScraper
from scrapers.moodys import MoodyScraper
from scrapers.sp_global import SPGlobalScraper
from scrapers.cornerstone import CornerstoneScraper
from scrapers.aei import AEIScraper
from scrapers.brattle import BrattleScraper
from scrapers.cra import CRAScraper
from scrapers.nera import NERAScraper
from scrapers.compass_lexecon import CompassLexeconScraper
from scrapers.analysis_group import AnalysisGroupScraper

SCRAPERS = [
    # ── Policy / research firms (some H-1B sponsorship) ──────────────────────
    FedReserveScraper,
    UrbanInstituteScraper,
    RandScraper,
    BrookingsScraper,
    MathematicaScraper,
    AbtScraper,
    AEIScraper,
    # ── Tech (H-1B sponsors) ─────────────────────────────────────────────────
    AmazonScraper,
    GoogleScraper,
    # ── Finance research (H-1B sponsors) ─────────────────────────────────────
    JPMorganScraper,
    MoodyScraper,
    SPGlobalScraper,
    # ── Economic consulting (strong H-1B sponsors, prime lane) ───────────────
    AnalysisGroupScraper,
    BrattleScraper,
    NERAScraper,
    CompassLexeconScraper,
    CRAScraper,
    CornerstoneScraper,
]


def run_all():
    db.init_db()
    print("=" * 50)
    print("JobPipeline — running all scrapers")
    print("=" * 50)

    total_new = 0
    results = []

    for ScraperClass in SCRAPERS:
        scraper = ScraperClass()
        new = scraper.run()
        results.append((scraper.COMPANY, new))
        total_new += new
        time.sleep(1)

    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for company, new in results:
        print(f"  {company}: {new} new job(s)")
    print(f"\nTotal new jobs added: {total_new}")

    all_jobs = db.list_jobs()
    print(f"Total jobs in pipeline: {len(all_jobs)}")

    stats = db.get_stats()
    by_status = stats.get("by_status", {})
    print(f"New (unreviewed): {by_status.get('New', 0)}")


if __name__ == "__main__":
    run_all()
