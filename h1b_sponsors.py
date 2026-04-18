"""
H1B sponsor detection.

get_h1b_status(company, description) → "Known Sponsor" | "No Sponsorship" | "Unknown"

Detection logic (in priority order):
  1. Company name contains a known-sponsor keyword → "Known Sponsor"
  2. Description contains an explicit no-sponsorship phrase → "No Sponsorship"
  3. Description contains an explicit sponsorship-offered phrase → "Known Sponsor"
  4. Otherwise → "Unknown"
"""

# ── Known H1B-sponsoring companies ───────────────────────────────────────────
# Lowercase substrings matched against the company name.
# Use specific-enough terms to avoid false positives.

KNOWN_SPONSOR_KEYWORDS = frozenset([
    # Research & policy orgs
    "rand corporation",
    "rand corp",
    "brookings",
    "urban institute",
    "mathematica",
    "abt associates",
    "abt global",
    "resources for the future",
    "national bureau of economic research",
    "nber",
    "pew research",
    "economic policy institute",
    "bipartisan policy",
    "milken institute",
    "center on budget",
    "center for american progress",
    "center for global development",
    "center for strategic",
    "migration policy institute",
    "peterson institute",
    "wilson center",
    "carnegie endowment",
    "cato institute",
    "heritage foundation",
    "american enterprise institute",
    "aei",
    "world resources institute",
    "human rights watch",

    # Federal Reserve System (all branches sponsor)
    "federal reserve",
    "fed reserve",

    # International organizations
    "world bank",
    "international monetary fund",
    "imf",
    "inter-american development bank",
    "asian development bank",
    "united nations",
    "oecd",

    # Big tech
    "amazon",
    "google",
    "microsoft",
    "meta ",   # space to avoid "metadata" etc.
    "apple inc",
    "netflix",
    "uber",
    "airbnb",
    "linkedin",
    "salesforce",
    "oracle",
    "ibm",
    "intel",
    "nvidia",
    "adobe",
    "twitter",
    "snap inc",
    "lyft",
    "stripe",
    "palantir",
    "databricks",
    "snowflake",

    # Finance & investment
    "jpmorgan",
    "jp morgan",
    "j.p. morgan",
    "goldman sachs",
    "morgan stanley",
    "blackrock",
    "vanguard",
    "fidelity investment",
    "bloomberg",
    "moody",
    "s&p global",
    "standard & poor",
    "deutsche bank",
    "barclays",
    "credit suisse",
    "ubs",
    "hsbc",
    "citigroup",
    "citibank",
    "bank of america",
    "wells fargo",
    "charles schwab",
    "bridgewater",
    "two sigma",
    "d.e. shaw",
    "citadel",
    "aqr capital",

    # Consulting & advisory
    "mckinsey",
    "boston consulting group",
    "bcg",
    "bain & company",
    "bain and company",
    "deloitte",
    "ernst & young",
    "ey ",
    "pricewaterhousecoopers",
    "pwc",
    "kpmg",
    "accenture",
    "oliver wyman",
    "roland berger",

    # Data & analytics
    "nielsen",
    "iri group",
    "sas institute",
    "veritas",
    "palantir",
    "tableau",

    # Healthcare & pharma (often sponsor for research roles)
    "johnson & johnson",
    "pfizer",
    "merck",
    "abbvie",
    "novartis",
    "roche",
    "genentech",

    # Staffing / research contractors
    "rti international",
    "rti ",
    "leidos",
    "mitre corporation",
    "mitre corp",
    "ida ",   # institute for defense analyses
    "booz allen",
    "cna analysis",
])

# ── Phrases that signal NO sponsorship in job descriptions ────────────────────

NO_SPONSORSHIP_PHRASES = (
    "will not sponsor",
    "unable to sponsor",
    "cannot sponsor",
    "not able to sponsor",
    "sponsorship is not available",
    "sponsorship not available",
    "no sponsorship",
    "does not sponsor",
    "we do not offer sponsorship",
    "visa sponsorship is not offered",
    "u.s. citizenship required",
    "must be a u.s. citizen",
    "must be a us citizen",
    "united states citizenship required",
    "active secret clearance required",
    "top secret clearance required",
    "ts/sci",
    "requires u.s. citizenship",
)

# ── Phrases that explicitly confirm sponsorship in descriptions ───────────────

SPONSORSHIP_OFFERED_PHRASES = (
    "will sponsor",
    "visa sponsorship available",
    "visa sponsorship provided",
    "we sponsor",
    "h-1b sponsorship",
    "h1b sponsorship",
    "sponsorship for work authorization",
    "able to sponsor",
    "open to sponsoring",
)


def get_h1b_status(company: str, description: str = "") -> str:
    """
    Returns "Known Sponsor", "No Sponsorship", or "Unknown".
    Pass the job description text for richer detection.
    """
    company_lower = (company or "").lower()
    desc_lower    = (description or "").lower()

    # 1. Company name match against known sponsor list
    for keyword in KNOWN_SPONSOR_KEYWORDS:
        if keyword in company_lower:
            return "Known Sponsor"

    # 2. Description: explicit no-sponsorship signal
    for phrase in NO_SPONSORSHIP_PHRASES:
        if phrase in desc_lower:
            return "No Sponsorship"

    # 3. Description: explicit sponsorship offer
    for phrase in SPONSORSHIP_OFFERED_PHRASES:
        if phrase in desc_lower:
            return "Known Sponsor"

    return "Unknown"
