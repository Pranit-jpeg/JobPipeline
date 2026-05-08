"""Prompt templates for resume tailoring + cover letter generation.

Single source of truth. Tune tone/constraints here, not in callers.

Identity placeholders (angle-bracket tokens like <name>, <school>, <program>)
are pre-baked at import time from profile.json, so the caller-facing format
strings only contain curly-brace placeholders for job-specific fields.
"""
from profile import PROFILE


def _bake(tmpl: str) -> str:
    """Substitute identity tokens from PROFILE, leaving curly-brace placeholders intact."""
    for key, val in PROFILE.items():
        tmpl = tmpl.replace(f"<{key}>", str(val))
    return tmpl


BANNED_PHRASES = [
    "delve",
    "delves",
    "in today's fast-paced",
    "synergize",
    "synergy",
    "results-driven",
    "leverage",
    "ecosystem",
    "game-changer",
    "move the needle",
    "hit the ground running",
    "best-in-class",
    "cutting-edge",
    "dynamic environment",
    "passionate about",
    "I am writing to",
    "It is my pleasure",
    "perfect fit",
    "robust",
    "seamless",
    "deep dive",
    "navigate the complexities",
    "tapestry",
    "bustling",
    "realm",
    "testament to",
    "ever-evolving",
]

ANTI_SLOP_RULES = f"""STYLE RULES — obey all:
1. NEVER use these phrases: {", ".join(BANNED_PHRASES)}.
2. No em-dashes (—) anywhere. Use periods, commas, or parentheses instead.
3. Mix short sentences (6-12 words) with longer ones. No paragraph should read like a rhythm machine.
4. Use specific numbers, proper nouns, and named projects pulled from the resume. No vague abstractions.
5. Do not repeat the same sentence opener consecutively (e.g., three sentences starting with "I").
6. Avoid over-using commas/semicolons to stack clauses. Break into two sentences when it helps.
7. No summary-of-the-obvious fluff ("As you know, your company is a leader in..."). Assume the reader knows their own company.
8. Write like a thoughtful person who read the posting once and knows their own resume cold. Not like a template."""


# ───────────────────────── Cover letter ─────────────────────────

COVER_LETTER_PROMPT = _bake("""You are helping <name>, a <program> student at <school> (graduating <grad_date>, <work_authorization>), write a cover letter for a specific job. Your job is to produce prose that reads as genuinely human AND is accessible to a non-specialist HR reader.

THE JOB
{job_context}

APPLICANT'S RESUME ({resume_version} version)
{resume_text}

═══════════════════════════════════════════════════════════
AUDIENCE CALIBRATION — READ FIRST
═══════════════════════════════════════════════════════════
The first reader is almost always a non-specialist HR screener, not the hiring manager. Default to plain English:
- Translate technical methods into action+outcome language. Instead of "applied a fixed-effects panel regression with clustered standard errors", say "ran a statistical model to isolate the policy's effect from other factors that varied year to year."
- Name a method by its term ONLY when the JD itself uses that term — then mirror the term verbatim (it doubles as ATS keyword coverage).
- Avoid stacking econometrics jargon. One technical term per paragraph is plenty.
- The reader should understand what the applicant DID and what HAPPENED, not need a stats degree to follow it.

═══════════════════════════════════════════════════════════
YOUR PROCESS — three steps, internal. Output the final letter only.
═══════════════════════════════════════════════════════════

STEP 1 — DRAFT
Produce a first draft using the format and constraints below.

COVER LETTER FORMAT — follow this structure exactly:

1. HEADER
   Today's date: {today_date}
   Hiring Manager
   {company}{company_address_line_full}

2. SALUTATION (REQUIRED — never omit)
   Dear Hiring Manager,

3. OPENING PARAGRAPH (2-4 sentences)
   Open with "I'm excited to apply for the [exact role title] position at {company}." Then a brief self-intro: recent graduate / <program> student at <school>, and a single concrete hook tied to why this specific role. Do NOT sound like a template.

4. {body_section_1_label} PARAGRAPH
   {body_section_1_guidance}

5. {body_section_2_label} PARAGRAPH
   {body_section_2_guidance}

6. {body_section_3_label} PARAGRAPH
   {body_section_3_guidance}

7. PASSION STATEMENT (CONDITIONAL — include only if the JD signals mission/values/impact heavily, e.g., public sector, non-profit, policy, research orgs; SKIP for generic corporate analyst roles)
   If included: one short paragraph (2-3 sentences) tying the applicant's background or motivation to the organization's stated mission. Must reference something specific from the JD, not generic "I care about impact" fluff.

8. CLOSING PARAGRAPH (1-2 sentences)
   A line like "I would be thrilled for the opportunity to discuss this position and I hope you will consider me as an addition to the team." Paraphrase so it does not read verbatim. No pushy call-to-action.

9. SIGN-OFF
   Sincerely,
   <name>

{anti_slop_rules}

HARD CONSTRAINTS
- Total body length: 350-450 words (not counting header/sign-off). Fit on one page.
- Every concrete claim must come from the resume above. Do not invent coursework, research, or experience.
- **TOOL/SKILL FIDELITY** (critical — this gets cross-checked against the resume): Do not name any tool, programming language, software product, package, or technical skill in the letter unless it appears verbatim somewhere in the resume above. Scan the resume's SKILLS block and work bullets first; if the tool isn't there (e.g. "SQL", "Power BI", "Tableau"), do not mention it — even if the JD asks for it. Topical relevance does not justify a claim the resume cannot support.
- **DURATION TRUTHFULNESS** (critical — recruiters cross-check this against the resume):
   - Never inflate how long the applicant did something. If the resume says "Sep 2025 – Dec 2025" (4 months), do NOT say "the past year", "over the past year", "for the last year", "spent a year", or any phrase implying ≥6 months.
   - Acceptable framings for short roles: "this past fall", "during my fall semester", "over four months in late 2025", or just lead with what was done without naming a duration at all.
   - If you reference duration, the duration in your prose must be ≤ the actual months between the resume's start and end dates.
   - Do NOT conflate "the past year of my MS program" with "the past year working at Employer X". If unsure, drop the duration phrase entirely.
- If you include a passion statement, it must name a specific thing from the JD (a program, mission, initiative, stated value), not a generic phrase.
- The letter must reference at least one specific detail from the JD (team name, tool, method, program, mission line) — this is how you prove you read it.
- For the role title, use the EXACT title from the JD, not a paraphrase.

STEP 2 — AUDIT THE DRAFT
Check it against this checklist:
A. **Audience** — is any sentence too jargon-heavy for an HR screener? Count technical terms per paragraph; flag paragraphs with 3+.
B. **Claim fidelity** — every concrete fact (employer, project, method, metric) must trace to the resume. Flag any that don't.
B2. **Tool/skill fidelity** — list every tool, programming language, software product, or technical skill named in the letter. For each, confirm it appears verbatim in the resume above. If any does not, REMOVE it from the letter in STEP 3. Common offenders: SQL, Power BI, Tableau, Excel, Python, R, Stata, SAS, MATLAB, AWS — verify each one explicitly.
C. **Duration truthfulness** — for every employer/role you reference, locate the dates in the resume. If your prose claims or implies a duration, does it match the resume? Flag any "past year"/"over a year"/"for X years" claims and verify against the resume dates. A 4-month role MUST NOT be described as a year.
D. **JD anchor** — at least one specific JD detail referenced (team name, program, tool, stated mission). Which one?
E. **Style rules** — any banned phrases? Any em-dashes? Any sentence opener repeated 3x?
F. **Length** — body word count between 350-450?
G. **Role title** — exact match to JD?

STEP 3 — REVISE
Apply every fix. Emit the final letter.

═══════════════════════════════════════════════════════════
OUTPUT FORMAT — respond with valid JSON only, no prose outside the JSON
═══════════════════════════════════════════════════════════
{{
  "audit_notes": [
    "Concrete finding from STEP 2 + what was changed in STEP 3.",
    "Example: 'Original second body paragraph stacked three econometric terms. Translated fixed-effects regression to plain-language description, kept difference-in-differences (it appears in the JD).'",
    "Example: 'JD anchor was generic — replaced with mention of the JD's stated focus on labor-market impact studies.'",
    "3-5 items. Only real findings."
  ],
  "used_passion_statement": true|false,
  "body_ordering": "{body_ordering_label}",
  "cover_letter_text": "full text with \\n\\n between paragraphs, starting from the date line and ending with <name>"
}}""")


# ───────────────────────── Resume tailor ─────────────────────────

RESUME_TAILOR_PROMPT = _bake("""You are helping <name> tailor a resume for a specific job. You will rephrase and reorder content to align with the JD, but you CANNOT add experience or facts that are not already in the base resume.

THE JOB
{job_context}

BASE RESUME ({resume_version})
{resume_text}

YOUR PROCESS — work through these four steps internally, then emit the final JSON only.

═══════════════════════════════════════════════════════════
STEP 1 — EXTRACT ATS KEYWORDS FROM THE JD
═══════════════════════════════════════════════════════════
Read the JD and pull 8-12 keywords/phrases that an ATS reader would key on:
- Hard skills and tools (e.g. "Stata", "Python", "Tableau", "regression analysis")
- Methods and frameworks (e.g. "difference-in-differences", "propensity score matching")
- Domain terms (e.g. "antitrust", "labor economics", "policy evaluation")
- Specific software, packages, certifications named in the JD

Rules:
- Use the EXACT string the JD uses. Do not paraphrase. ATS systems match literal substrings — "causal inference" and "causal analysis" do not count as the same.
- Pull only terms actually present in the JD. Don't add aspirational keywords.
- If the JD lists a skill the base resume doesn't support, still extract it (you'll mark it "not supported" in the audit and skip it from the resume).

═══════════════════════════════════════════════════════════
STEP 2 — DRAFT THE TAILORED RESUME
═══════════════════════════════════════════════════════════
Apply these constraints to produce a first draft:

1. Every work-experience bullet must be traceable to a bullet in the base resume. You may rephrase phrasing and swap vocabulary to match JD terminology, but you cannot invent new accomplishments, change numbers, or fabricate projects.
2. You MAY reorder bullets within a role so the most JD-relevant bullet appears first.
3. You MAY rewrite the PROFESSIONAL SUMMARY to target this specific JD (2-3 sentences). This section is a pitch, not a claim of experience, so rewriting is fine as long as it is grounded in the resume.
4. You MAY reorder the SKILLS lists so JD-relevant terms appear earlier. You can add a skill ONLY if it is already demonstrated somewhere in the resume bullets. Do not add skills out of thin air.
5. Do NOT change company names, job titles, dates, GPA, degree, school names, or research paper titles.
6. Do NOT add length. The resume must fit on one page. Aim for total bullet count equal to or less than the base.
7. **Bullet length — count CHARACTERS, not words.** PDF line wrap is character-driven. The rendered resume has ~125 characters of usable line width at typical tightness. Three zones:
   - **Single-line bullet:** ≤ 130 characters.
   - **Two-line bullet (PREFERRED):** 220-245 characters. Fills both lines almost fully.
   - **BAD ZONE — strictly avoid: 131-219 characters.** Wraps to a 2nd line with only 1-3 words ("indicators.", "engagement.") leaving ugly white space.
   - **OVER-EXPAND — strictly avoid: > 245 characters.** Wraps to 3 lines with line 3 being a stub like "segments." — worse than the original bad zone.
   - Hard cap: 245 characters per bullet.
   - **User preference: rich 2-line bullets over short 1-liners.** When tailoring, default to producing 220-245 char bullets that fill 2 lines, NOT to compressing everything to 1 line. Only use single-line bullets when the base content genuinely doesn't have enough material for 2 lines.
   - **How to fix bad-zone bullets (131-219 chars):**
     - PREFERRED: EXPAND to 220-245 chars by adding legitimate detail from the BASE RESUME bullet — a method name, specific number, tool, dataset, or context that was already in the source. NEVER fabricate.
     - FALLBACK: TRIM to ≤130 chars only when the base resume has no more detail worth surfacing.
   - Count characters precisely. The model has a tendency to undercount; literally count chars before deciding. NEVER produce a bullet > 245 chars under any circumstance.
8. Lead with a strong verb, keep concrete metrics, drop filler ("responsible for", "successfully", "in order to").
9. **Professional summary length** — match the base resume's length, don't shorten it:
   - Target: 3 sentences, 45-55 words, which renders as 3 full lines on the PDF. This is what the base resume summaries are calibrated to.
   - DO NOT compress to 2 sentences "for tightness" — a compressed summary leaves a half-empty trailing line on the PDF and looks unfinished.
   - Acceptable safe zones if you genuinely need a shorter summary: ≤16 words (1 full line) or ~30 words / 2 sentences (2 full lines). Otherwise default to the 45-55 word / 3-sentence target.
   - AVOID partial-line lengths (17-29 words, 31-44 words) — these all produce a trailing line that's mostly blank.
10. ATS keyword integration: where the base resume supports it, weave the verbatim keywords from STEP 1 into the bullets, skills lists, or summary. Don't force keywords into places that don't fit naturally — this is about surfacing keywords the resume already supports.
11. **Preserve every section that exists in the base resume.** If the base resume has an ACADEMIC PROJECTS section (or similar), keep it in the output. Don't silently drop sections.
12. **No phrase repetition between adjacent bullets within the same role.** Within any one work-experience entry, two consecutive bullets must not share a multi-word phrase of 4+ words verbatim. Example BAD: bullet 1 ends "across inventory, AP/AR, and vendor records for 25+ staff" and bullet 2 begins "Managed operational data across inventory, AP/AR, and vendor records for 25+ staff." Vary the framing — swap synonyms, drop the duplicated qualifier from the second bullet, or fold one bullet into the other if both are saying the same thing. Repeating a phrase across DIFFERENT roles (e.g. mentioning "Excel" in both Aditya and Boston) is fine; the constraint is per-role.

═══════════════════════════════════════════════════════════
STEP 3 — SELF-AUDIT THE DRAFT
═══════════════════════════════════════════════════════════
Run the draft against this checklist. Be honest — flag real issues, don't invent ones:

A. **Traceability** — pick any 2-3 bullets and explicitly verify each maps to a base-resume bullet. Note which base bullet.
B. **Keyword coverage** — for each keyword from STEP 1, mark it (i) present in tailored resume, (ii) supported by base but missing → fix, (iii) not supported by base → skip.
C. **Wrap-zone violations — CRITICAL CHECK.** For EVERY bullet in the draft (work experience AND academic projects), count its character length precisely. Flag two kinds of violations:
   - 131-219 chars (bad zone): MUST be fixed in STEP 4 — preferably EXPAND to 220-245 chars using base-resume detail, fallback TRIM to ≤130.
   - >245 chars (over-expand): MUST be fixed in STEP 4 — TRIM to either ≤245 chars (if 2-line) or ≤130 (if 1-line). Anything over 245 wraps to 3 lines.
   List EVERY violating bullet here with its char count and the fix to apply: e.g. "City of Boston bullet 1 = 268 chars → trim to 240"; "Circadian bullet 2 = 144 chars → expand to 230 by restoring 'paid Kolabtree engagement' context". If clean, say so explicitly so the user can verify the audit ran.
D. **Fabrication check** — list any specific facts (numbers, project names, employers, methods) you added that are NOT in the base resume. If any, flag them for removal.
D2. **Adjacent-bullet repetition check.** For each work-experience role, scan every consecutive pair of bullets. Flag any pair that shares a verbatim multi-word phrase of 4+ words (ignore single duplicated terms like "data" or "team"). For each flag, decide in STEP 4: (a) drop the repeated phrase from the second bullet, (b) rephrase the second bullet so the overlap collapses, or (c) merge the two bullets if they are actually saying the same thing. List the offending phrase and the role: e.g. "Aditya bullets 1+2 both contain 'across inventory, AP/AR, and vendor records for 25+ staff' → drop from bullet 2."
E. **Length / one-page fit** — total bullet count vs base. If you added bullets, flag.
F. **Hard-set fields** — confirm name, contact, school, degree, dates, GPA all match base resume.

═══════════════════════════════════════════════════════════
STEP 4 — REVISE
═══════════════════════════════════════════════════════════
Apply every fix flagged in STEP 3 to produce the final version. The audit_notes you emit in the JSON should describe what STEP 3 found AND what you fixed in this step. Be specific (e.g. "Bullet 'Conducted analysis of survey data' was 18 words and would wrap badly — trimmed to 11 words: 'Analyzed 2,000-respondent labor survey using Stata regressions.'"). 3-6 items.

═══════════════════════════════════════════════════════════
OUTPUT FORMAT — respond with valid JSON only, no prose outside the JSON
═══════════════════════════════════════════════════════════
{{
  "ats_keywords": ["verbatim term 1", "verbatim term 2", "..."],
  "audit_notes": [
    "Concrete finding from STEP 3 + what was changed in STEP 4. Example: 'JD keyword `difference-in-differences` was missing from bullets despite base resume supporting it — added to City of Boston bullet.'",
    "Example: 'Bullet about Pratham survey was 19 words (would wrap badly) — trimmed to 12.'",
    "3-6 items. Only real findings, no filler."
  ],
  "name": "<name_upper>",
  "contact_line": "<contact_line>",
  "professional_summary": "3-sentence tailored summary, ~45-55 words (matches base resume length, fills 3 full lines on the PDF)",
  "work_experience": [
    {{
      "company": "example employer",
      "location": "City, State",
      "dates": "Start – End",
      "role": "Role Title",
      "bullets": ["bullet 1 text", "bullet 2 text", "..."]
    }}
  ],
  "education": [
    {{
      "school": "<school>",
      "location": "<base_location>",
      "dates": "Start – <grad_date>",
      "degree_line": "Degree | Concentration | GPA",
      "courses": "Courses: ...",
      "research": "Research: ..."
    }}
  ],
  "skills": {{
    "Analytical": "comma-separated list",
    "Tools": "comma-separated list",
    "Languages": "comma-separated list"
  }},
  "academic_projects": [
    {{
      "name": "Project Name | Source/Course",
      "bullets": ["short bullet text"]
    }}
  ],
  "changes_summary": [
    "Concrete description of an edit versus the base resume.",
    "e.g. 'Rewrote professional summary to emphasize econometric consulting and antitrust framing.'",
    "e.g. 'Reordered bullets: moved the causal-inference project to first position.'",
    "3-6 items. Only real edits."
  ]
}}

Notes on `academic_projects`:
- Include ONLY if the base resume has an ACADEMIC PROJECTS / PROJECTS / RESEARCH PROJECTS section. Otherwise emit an empty list.
- Each project entry mirrors a project block from the base. Project name should include any source attribution from the base (e.g. "Unsupervised ML & Data Mining | Northeastern").
- Same character-based wrap-zone rule: ≤130 chars (1 line) or 220-245 chars (2 full lines). Avoid 131-219 and >245.""")
