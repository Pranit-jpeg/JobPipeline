# JOB PIPELINE PROJECT — MASTER BRIEF
# Created: April 14, 2026
# Author: Pranit Choudhary
# Purpose: Build a systematic job search pipeline with direct company scraping + Kanban dashboard

## ABOUT ME (for Claude Code context)
- MS Economics, Northeastern University (graduating May 2026), Minor: Data Science
- BSc Economics, NMIMS Mumbai, Minor: Finance
- F-1 visa, STEM OPT (36 months post-graduation), will need H-1B sponsorship after
- Based in Boston, MA
- Does NOT know SQL — never list SQL as a skill
- Proficient in: Python, R, Stata, Excel, Tableau
- Target roles: Economics, Policy Analysis, Research Analysis, Data Analysis, Quantitative roles
- Target locations: Boston, NYC, DC, Chicago, SF, LA, Seattle, Philadelphia, Denver, Remote
- Experience: City of Boston (policy evaluation), Circadian Connect (research), Aditya Process (operations), Pratham (surveys)

## PROJECT GOAL
Build a local job search pipeline that:
1. Scrapes jobs DIRECTLY from target company career pages (not just LinkedIn/Indeed)
2. Stores jobs in a local database (SQLite or JSON)
3. Displays a Kanban-style dashboard (web app) for tracking application progress
4. Allows manual job additions
5. Runs daily scraping with deduplication
6. Focuses on QUALITY over QUANTITY — 3-5 focused applications per day

## TARGET COMPANIES TO SCRAPE (Direct Career Pages)
### Tier 1: Economics/Policy/Research Organizations
- Federal Reserve Banks (Boston, NY, Chicago, SF, etc.)
- Brookings Institution
- Urban Institute
- RAND Corporation
- RTI International
- Mathematica
- Abt Associates
- NBER
- Congressional Budget Office (CBO)
- Government Accountability Office (GAO)
- Bureau of Labor Statistics (BLS)
- Bureau of Economic Analysis (BEA)
- World Bank
- IMF
- Brattle Group
- Analysis Group
- Charles River Associates
- NERA Economic Consulting
- Compass Lexecon

### Tier 2: Think Tanks & Policy
- American Enterprise Institute
- Cato Institute
- Center on Budget and Policy Priorities
- Economic Policy Institute
- Peterson Institute
- Aspen Institute
- Council on Foreign Relations
- Carnegie Endowment
- New America

### Tier 3: Tech/Finance (Economics teams)
- Amazon (Economics team)
- Uber (Economics team)
- Airbnb (Economics team)
- Google (Public Policy / Strategy & Ops)
- Meta (Economics team)
- Microsoft (Economics team)
- Anthropic (Economic Research)
- Netflix (Data/Research)
- JPMorgan (Research)
- Goldman Sachs (Research)
- Morgan Stanley (Research)
- Bank of America (Research)
- Moody's
- S&P Global
- Fitch

### Tier 4: Government
- USAJobs.gov (keyword search)
- NYC government jobs
- City of Boston jobs
- State of Massachusetts jobs
- State of California jobs

## TECH STACK (Suggested)
- Backend: Python (FastAPI or Flask)
- Scraping: BeautifulSoup, Selenium, or Playwright for JS-rendered pages
- Database: SQLite (local, simple, no server needed)
- Frontend Dashboard: React or simple HTML/JS with Tailwind
- Scheduling: Python schedule library or cron jobs
- Deduplication: Hash job title + company + location

## KANBAN BOARD COLUMNS
1. "New" — freshly scraped, unreviewed
2. "Interested" — worth applying to
3. "Applied" — application submitted
4. "Interview" — got a response/interview
5. "Offer" — received offer
6. "Rejected" — rejected or no response after 30 days
7. "Skipped" — reviewed but not interested

## JOB CARD FIELDS
- Job title
- Company name
- Location
- Salary (if available)
- URL (direct link to application)
- Date scraped
- Date applied
- Resume version used (Econ/Policy, Finance, Data Analyst, Research)
- Notes field
- H-1B sponsor status (Known/Unknown)
- Source (which career page it came from)
- Status (Kanban column)

## DAILY WORKFLOW
1. Run scraper (morning)
2. Review "New" jobs (10 min)
3. Move best 3-5 to "Interested"
4. Apply to "Interested" jobs with tailored materials
5. Move to "Applied" with notes

## FOLDER STRUCTURE
JobPipeline/
├── docs/           # This brief + any reference docs
├── scrapers/       # Individual scraper scripts per company/source
├── dashboard/      # Frontend dashboard code
├── data/           # SQLite database + any cached data
├── resumes/        # PDF copies of 4 resume versions
└── README.md       # Setup instructions

## RESUME VERSIONS AVAILABLE
1. Resume_EconPolicy.pdf — for economics, policy, government roles
2. Resume_FinanceConsulting.pdf — for finance, banking, consulting roles
3. Resume_DataAnalyst.pdf — for data analyst, data science roles
4. Resume_ResearchAnalyst.pdf — for research, academic, think tank roles

## IMPORTANT CONSTRAINTS
- No SQL knowledge — don't use SQL-heavy solutions
- Must run on Windows (user's machine)
- Keep it simple — SQLite, not Postgres
- Must be maintainable by someone who's not a natural coder
- AI tools (Claude, ChatGPT) will be used for assistance — that's fine
