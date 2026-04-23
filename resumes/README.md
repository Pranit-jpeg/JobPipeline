# resumes/

The scoring pipeline (`score_jobs.py`) reads four plain-text resume files from
this folder and scores each newly scraped job against all four using Claude
Haiku. The resume with the highest score is recorded as the job's best-fit
version.

The actual resume files are gitignored — they contain personal contact
information and aren't intended for public distribution. If you're cloning
this repo to use the pipeline yourself, you'll need to create your own.

## Required files

Create these four files in this folder, with exactly these names:

| Filename | Used for |
|---|---|
| `data_analyst.txt` | Data analyst / analytics engineer roles |
| `econ_policy.txt` | Economic research, think tanks, policy shops |
| `finance_consulting.txt` | Finance, banking, economic consulting |
| `research_analyst.txt` | Academic / pre-doc research roles |

The labels that appear in the scoring output (`DataAnalyst`, `EconPolicy`,
`FinanceConsulting`, `ResearchAnalyst`) are defined in
`score_jobs.py:RESUME_FILES`.

## Format

Plain UTF-8 text. No special structure is required — the scorer passes the
raw text to the model. A reasonable layout:

```
YOUR NAME
contact line (linkedin | email | phone | city | github)

PROFESSIONAL SUMMARY
2–4 sentences.

WORK EXPERIENCE
Role, Company, Location | Dates
- bullet
- bullet

EDUCATION
...

SKILLS
...
```

Each file is capped at 3000 characters before being sent to the model
(`score_jobs.py:45`), so keep them tight — one page of plain text is plenty.

## PDFs

If you want to keep PDF copies of your resumes in this folder (e.g. for the
`generation/` tool or for manual use), put them here with any filename.
`resumes/*.pdf` is gitignored, so they won't be published.
