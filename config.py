import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "data", "jobs.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "scrape_log.txt")

STATUSES = ["New", "Interested", "Applied", "Interview", "Offer", "Rejected", "Skipped"]

RESUME_VERSIONS = ["EconPolicy", "FinanceConsulting", "DataAnalyst", "ResearchAnalyst"]
