# CLAUDE CODE PROMPTS — JobPipeline Project
# Use these prompts IN ORDER in Claude Code
# Set up this project folder as a Claude Code Project first
# Each prompt is one "task" for Claude Code

# ============================================
# HOW TO SET UP CLAUDE CODE (if never used before)
# ============================================
# 1. Install Claude Code: Go to https://claude.ai/download and install the desktop app
#    OR install via terminal: npm install -g @anthropic-ai/claude-code
# 2. Open your terminal/command prompt
# 3. Navigate to the project: cd C:\Users\prani\Desktop\JobPipeline
# 4. Run: claude
# 5. Claude Code will now use this folder as context
# 6. You can also set this as a "Project" in Claude Code settings
#    so it always has the docs/PROJECT_BRIEF.md as reference

# ============================================
# PROMPT 1: Project Initialization
# ============================================

"""
Read the file docs/PROJECT_BRIEF.md to understand the full project context.

I want to build a job search pipeline with:
1. A SQLite database to store scraped jobs
2. Python scrapers that pull jobs from company career pages
3. A web-based Kanban dashboard to track applications

Start by:
- Setting up the Python project structure (requirements.txt, main config)
- Creating the SQLite database schema with these fields per job:
  id, title, company, location, salary, url, date_scraped, date_applied,
  resume_version, notes, h1b_status, source, status
- Status should be one of: New, Interested, Applied, Interview, Offer, Rejected, Skipped
- Create a simple db.py module with functions to add, update, list, and search jobs
- Make sure I don't need to know SQL — all database operations should be wrapped in Python functions

Do NOT use SQL directly in any user-facing code. Wrap everything in clean Python functions.
"""

# ============================================
# PROMPT 2: Build First Scraper (Federal Reserve)
# ============================================

"""
Now build the first scraper. Start with the Federal Reserve Bank of Boston careers page.

Requirements:
- Use BeautifulSoup or Playwright (whichever works better for the site)
- Navigate to their careers/jobs page
- Search for keywords: economist, research, analyst, data
- Extract: job title, location, URL, and date posted if available
- Save results to our SQLite database with status="New"
- Handle deduplication (don't add the same job twice — use URL as unique key)
- Print a summary of new jobs found

Save the scraper as scrapers/fed_boston.py
Also create a scrapers/base.py with a BaseScraper class that other scrapers can inherit from.

Test the scraper and show me the results.
"""

# ============================================
# PROMPT 3: Add More Scrapers (Batch)
# ============================================

"""
Using the BaseScraper pattern from scrapers/base.py, build scrapers for these organizations.
Each one should be its own file in scrapers/:

1. scrapers/brookings.py — Brookings Institution careers
2. scrapers/urban_institute.py — Urban Institute careers
3. scrapers/rand.py — RAND Corporation careers
4. scrapers/mathematica.py — Mathematica careers
5. scrapers/abt.py — Abt Associates careers

For each scraper:
- Find their careers page URL
- Search for keywords: economist, research analyst, data analyst, policy analyst, quantitative
- Extract job title, location, URL, date if available
- Save to SQLite with deduplication
- If the site uses JavaScript rendering, use Playwright instead of BeautifulSoup

Also create a scrapers/run_all.py that runs all scrapers in sequence and prints a summary.
"""

# ============================================
# PROMPT 4: Add Government Job Board Scrapers
# ============================================

"""
Build scrapers for government job boards:

1. scrapers/usajobs.py — USAJobs.gov
   - Use their public API (https://developer.usajobs.gov/)
   - Search for: economist, economic analyst, policy analyst, research analyst, data analyst
   - Filter: entry-level (GS-5 through GS-11)
   - Location: Boston, NYC, DC, Chicago, SF, Remote

2. scrapers/nyc_gov.py — NYC government jobs (cityjobs.nyc.gov)
   - Search for analyst, economist, research roles

3. scrapers/mass_gov.py — Massachusetts state jobs
   - Search for analyst, economist, research roles

Add these to run_all.py
"""

# ============================================
# PROMPT 5: Add Tech/Finance Company Scrapers
# ============================================

"""
Build scrapers for tech and finance companies that have economics teams:

1. scrapers/amazon.py — Amazon jobs (search: economist, economic)
2. scrapers/google.py — Google careers (search: economist, policy analyst, strategy)
3. scrapers/jpmorgan.py — JPMorgan careers (search: research analyst, economist, quantitative)
4. scrapers/moodys.py — Moody's careers (search: economist, research analyst)
5. scrapers/sp_global.py — S&P Global careers (search: economist, research analyst)

These sites are more complex (heavy JavaScript). Use Playwright for these.
Filter for entry-level or associate-level roles only.
Add to run_all.py
"""

# ============================================
# PROMPT 6: Build the Kanban Dashboard (Backend API)
# ============================================

"""
Build a Flask/FastAPI backend that serves our job data as a REST API:

Endpoints:
- GET /api/jobs — list all jobs, filterable by status, company, resume_version
- GET /api/jobs/<id> — get single job details
- PUT /api/jobs/<id> — update job (change status, add notes, set resume_version, set date_applied)
- POST /api/jobs — manually add a new job
- DELETE /api/jobs/<id> — delete a job
- GET /api/stats — summary stats (count per status, count per resume_version)

Save as dashboard/api.py
The API should read from our SQLite database in data/jobs.db
"""

# ============================================
# PROMPT 7: Build the Kanban Dashboard (Frontend)
# ============================================

"""
Build a clean, minimal Kanban-style web dashboard using HTML/CSS/JS (no React needed — keep it simple).

Features:
- 7 columns: New, Interested, Applied, Interview, Offer, Rejected, Skipped
- Each job is a card showing: title, company, location, and resume version (color-coded)
- Cards are draggable between columns (drag-and-drop to change status)
- Click a card to see full details + edit notes + set resume version + add date applied
- Color coding by resume version:
  - Econ/Policy = green tint
  - Finance/Consulting = blue tint
  - Data Analyst = orange tint
  - Research Analyst = purple tint
- A counter showing how many jobs are in each column
- A search/filter bar at the top
- An "Add Job" button for manual entry
- Stats panel showing: total jobs, applied count, interview count, response rate

Save as dashboard/index.html, dashboard/style.css, dashboard/app.js
The frontend should call our Flask/FastAPI backend API.

The dashboard should be usable and clean — not fancy, but professional and functional.
"""

# ============================================
# PROMPT 8: Create the Daily Run Script
# ============================================

"""
Create a main run.py script in the project root that:

1. Runs all scrapers (scrapers/run_all.py)
2. Prints a summary: X new jobs found today, Y total jobs in pipeline
3. Starts the dashboard server so I can review jobs in my browser
4. Opens the browser automatically to http://localhost:3000

Also create a scrape_only.py that just runs scrapers without starting the dashboard.

Add a simple logging system so I can see what happened during each scrape run.
Save logs to data/scrape_log.txt with timestamps.
"""

# ============================================
# PROMPT 9: Add H-1B Sponsor Detection
# ============================================

"""
Add a feature to detect likely H-1B sponsors:

1. Create a data/known_sponsors.json file with a list of known H-1B sponsoring companies
   (include major universities, consulting firms, banks, tech companies, federal contractors)
2. When a job is scraped, automatically check if the company matches a known sponsor
3. Set h1b_status to "Known Sponsor" if matched, "Unknown" otherwise
4. Display sponsor status on the Kanban card with a visual indicator (green checkmark for known sponsors)

Use this H-1B sponsor database as a starting reference: https://www.myvisajobs.com/Reports/2024-H1B-Visa-Sponsor.aspx
Don't scrape the site — just manually compile the top 200-300 companies into the JSON file.
"""

# ============================================
# PROMPT 10: Polish and Test
# ============================================

"""
Final polish:

1. Test all scrapers and fix any that are broken
2. Make sure the dashboard loads correctly and drag-and-drop works
3. Add error handling to scrapers (timeouts, rate limiting, retry logic)
4. Add a "Last scraped" timestamp display on the dashboard
5. Create a one-click batch file (run.bat) for Windows that:
   - Activates the virtual environment
   - Runs scrapers
   - Starts the dashboard
   - Opens the browser
6. Update README.md with final setup instructions

Run everything end-to-end and show me the results.
"""

# ============================================
# TIPS FOR USING CLAUDE CODE
# ============================================
# 1. Always start by telling Claude Code to read docs/PROJECT_BRIEF.md
# 2. Do ONE prompt at a time — don't rush through all 10 in one session
# 3. Test each step before moving to the next
# 4. If something breaks, paste the error and ask Claude Code to fix it
# 5. Save your work frequently (Claude Code auto-saves to files)
# 6. If you need to add a new company scraper later, just say:
#    "Build a scraper for [company name] following the BaseScraper pattern"
