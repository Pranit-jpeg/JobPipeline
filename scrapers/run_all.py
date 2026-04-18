"""
Run all scrapers in sequence and print a summary.
Usage: python -m scrapers.run_all
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from scrapers.fed_boston import FedReserveScraper
from scrapers.urban_institute import UrbanInstituteScraper
from scrapers.rand import RandScraper
from scrapers.brookings import BrookingsScraper
from scrapers.mathematica import MathematicaScraper
from scrapers.abt import AbtScraper
from scrapers.usajobs import USAJobsScraper
from scrapers.nyc_gov import NYCGovScraper
from scrapers.mass_gov import MassGovScraper
from scrapers.amazon import AmazonScraper
from scrapers.google import GoogleScraper
from scrapers.jpmorgan import JPMorganScraper
from scrapers.moodys import MoodyScraper
from scrapers.sp_global import SPGlobalScraper
# ── New scrapers from friend's list ──────────────────────────────────────────
from scrapers.treasury import TreasuryScraper
from scrapers.usda_ers import USDAScraper
from scrapers.cornerstone import CornerstoneScraper
from scrapers.uchicago import UChicagoScraper
from scrapers.bfi import BFIScraper
from scrapers.aei import AEIScraper
from scrapers.brattle import BrattleScraper
from scrapers.cra import CRAScraper
from scrapers.jpab import JPALScraper
from scrapers.predoc import PredocScraper
from scrapers.harvard import HarvardScraper
# GoldmanSachsScraper — blocks headless browsers, skipped
# MicrosoftScraper — blocks headless browsers, skipped
from scrapers.nera import NERAScraper
from scrapers.compass_lexecon import CompassLexeconScraper
from scrapers.mit import MITScraper
from scrapers.stanford import StanfordScraper

SCRAPERS = [
    # ── Original scrapers ─────────────────────────────────────────────────────
    FedReserveScraper,
    UrbanInstituteScraper,
    RandScraper,
    BrookingsScraper,
    MathematicaScraper,
    AbtScraper,
    USAJobsScraper,
    NYCGovScraper,
    MassGovScraper,
    AmazonScraper,
    GoogleScraper,
    JPMorganScraper,
    MoodyScraper,
    SPGlobalScraper,
    # ── New scrapers ──────────────────────────────────────────────────────────
    TreasuryScraper,
    USDAScraper,
    CornerstoneScraper,
    UChicagoScraper,
    BFIScraper,
    AEIScraper,
    BrattleScraper,
    CRAScraper,
    JPALScraper,
    PredocScraper,
    HarvardScraper,
    NERAScraper,
    CompassLexeconScraper,
    MITScraper,
    StanfordScraper,
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
