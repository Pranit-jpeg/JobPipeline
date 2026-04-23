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

COVER_LETTER_PROMPT = _bake("""You are helping <name>, a <program> student at <school> (graduating <grad_date>, <work_authorization>), write a cover letter for a specific job. Your job is to produce prose that reads as genuinely human.

THE JOB
{job_context}

APPLICANT'S RESUME ({resume_version} version)
{resume_text}

COVER LETTER FORMAT — follow this structure exactly:

1. HEADER
   Today's date: {today_date}
   Hiring Manager
   {company}
   {company_address_line}

2. OPENING PARAGRAPH (2-4 sentences)
   Open with "I'm excited to apply for the [exact role title] position at {company}." Then a brief self-intro: recent graduate / <program> student at <school>, and a single concrete hook tied to why this specific role. Do NOT sound like a template.

3. {body_section_1_label} PARAGRAPH
   {body_section_1_guidance}

4. {body_section_2_label} PARAGRAPH
   {body_section_2_guidance}

5. {body_section_3_label} PARAGRAPH
   {body_section_3_guidance}

6. PASSION STATEMENT (CONDITIONAL — include only if the JD signals mission/values/impact heavily, e.g., public sector, non-profit, policy, research orgs; SKIP for generic corporate analyst roles)
   If included: one short paragraph (2-3 sentences) tying the applicant's background or motivation to the organization's stated mission. Must reference something specific from the JD, not generic "I care about impact" fluff.

7. CLOSING PARAGRAPH (1-2 sentences)
   A line like "I would be thrilled for the opportunity to discuss this position and I hope you will consider me as an addition to the team." Paraphrase so it does not read verbatim. No pushy call-to-action.

8. SIGN-OFF
   Sincerely,
   <name>

{anti_slop_rules}

HARD CONSTRAINTS
- Total body length: 350-450 words (not counting header/sign-off). Fit on one page.
- Every concrete claim must come from the resume above. Do not invent coursework, research, or experience.
- If you include a passion statement, it must name a specific thing from the JD (a program, mission, initiative, stated value), not a generic phrase.
- The letter must reference at least one specific detail from the JD (team name, tool, method, program, mission line) — this is how you prove you read it.
- For the role title, use the EXACT title from the JD, not a paraphrase.

OUTPUT FORMAT
Respond with valid JSON only, no prose outside the JSON:
{{
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

YOUR TASK
Produce a tailored version of this resume as structured JSON. Rules:

1. Every work-experience bullet in your output must be traceable to a bullet in the base resume. You may rephrase phrasing and swap vocabulary to match JD terminology, but you cannot invent new accomplishments, change numbers, or fabricate projects.
2. You MAY reorder bullets within a role so the most JD-relevant bullet appears first.
3. You MAY rewrite the PROFESSIONAL SUMMARY to target this specific JD (2-3 sentences). This section is a pitch, not a claim of experience, so rewriting is fine as long as it is grounded in the resume.
4. You MAY reorder the SKILLS lists (Analytical first / Tools first) so JD-relevant terms appear earlier. You can add a skill ONLY if it is already demonstrated somewhere in the resume bullets. Do not add skills out of thin air.
5. Do NOT change company names, job titles, dates, GPA, degree, school names, or research paper titles.
6. Do NOT add length. The resume must fit on one page. Aim for total bullet count equal to or less than the base.
7. Keep every bullet concise: HARD CAP 30 words / 200 characters per bullet. If a base bullet is longer, shorten it — do not preserve its length. Lead with the verb, keep metrics, drop filler.
8. Keep the professional summary to 2 sentences maximum (no more than 55 words total).

OUTPUT FORMAT — respond with valid JSON only:
{{
  "name": "<name_upper>",
  "contact_line": "<contact_line>",
  "professional_summary": "2-3 sentence tailored summary",
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
  "changes_summary": [
    "Concrete, specific description of an edit you made versus the base resume.",
    "e.g. 'Rewrote professional summary to emphasize econometric consulting and antitrust framing.'",
    "e.g. 'Reordered bullets: moved the causal-inference project to first position.'",
    "e.g. 'Rephrased an audit bullet to use the JD term operational due diligence.'",
    "3-6 items. Do NOT include changes you did not actually make. If nothing changed in a section, do not invent an entry for it."
  ]
}}""")
