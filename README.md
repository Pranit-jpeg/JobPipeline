# JobPipeline

A systematic job search pipeline with direct company career page scraping and a Kanban dashboard for tracking applications.

## Setup
1. Install Python 3.10+
2. Install Node.js 18+
3. Run `pip install -r requirements.txt`
4. Run `cd dashboard && npm install`
5. Run `python run.py` to start the dashboard

## Project Structure
- `docs/` — Project brief and reference documents
- `scrapers/` — Individual scraper scripts per company/source
- `dashboard/` — Frontend Kanban dashboard
- `data/` — SQLite database
- `resumes/` — PDF copies of 4 resume versions

## Daily Usage
1. Run `python scrape.py` to scrape new jobs
2. Open dashboard at `http://localhost:3000`
3. Review "New" jobs, move best 3-5 to "Interested"
4. Apply with tailored materials
5. Update status in dashboard

## Built with Claude Code as a project
