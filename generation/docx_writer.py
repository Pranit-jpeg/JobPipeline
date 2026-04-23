"""Render tailored resume + cover letter to .docx, then convert to PDF.

Single-page style: centered caps name, ruled section headers, em-dash bullets,
tight margins. Supports a `tightness` parameter (0-3) that progressively
shrinks fonts/margins so the orchestrator can auto-fit overflow content back
onto a single page.
"""
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from profile import PROFILE


# ───────────────────────── style levels ─────────────────────────

# Each level dials margins/fonts tighter. Level 0 matches the original PDF.
# Level 4 is the final safety net — dense but still legible.
def _style(tightness: int) -> dict:
    t = max(0, min(4, int(tightness)))
    margins_tb = [0.5, 0.42, 0.38, 0.35, 0.30][t]
    margins_lr = [0.6, 0.5, 0.45, 0.4, 0.35][t]
    body = [10.0, 9.5, 9.5, 9.0, 8.5][t]
    section = [11.0, 11.0, 10.5, 10.5, 10.0][t]
    name = [18.0, 18.0, 17.5, 17.0, 16.5][t]
    contact = [9.0, 9.0, 9.0, 8.5, 8.0][t]
    role = body
    company = body + 0.5
    line = [1.12, 1.08, 1.04, 1.0, 0.98][t]
    return dict(
        margins_tb=margins_tb, margins_lr=margins_lr,
        name=Pt(name), contact=Pt(contact), section=Pt(section),
        body=Pt(body), role=Pt(role), company=Pt(company),
        line=line,
    )


# ───────────────────────── helpers ─────────────────────────

NAME_FONT = "Calibri"
BODY_FONT = "Calibri"

# Public profile URLs — used to turn "LinkedIn" / "GitHub" tokens in the
# contact line into real hyperlinks on the rendered resume.
LINKEDIN_URL = PROFILE["linkedin_url"]
GITHUB_URL   = PROFILE["github_url"]


def _set_margins(doc, top, bottom, left, right):
    for section in doc.sections:
        section.top_margin = Inches(top)
        section.bottom_margin = Inches(bottom)
        section.left_margin = Inches(left)
        section.right_margin = Inches(right)


def _tight(paragraph, space_before=0, space_after=0, line=1.0):
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = line


def _add_bottom_border(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_run(paragraph, text, *, bold=False, italic=False, size=None, font=BODY_FONT):
    run = paragraph.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.name = font
    if size is not None:
        run.font.size = size
    return run


def _add_hyperlink(paragraph, url, text, *, size=None, font=BODY_FONT):
    """Append a hyperlink run to `paragraph`. python-docx has no native API for
    this, so we write the OOXML directly.
    """
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), font)
    rFonts.set(qn("w:hAnsi"), font)
    rPr.append(rFonts)

    if size is not None:
        sz = OxmlElement("w:sz")
        # OOXML sizes are in half-points
        sz.set(qn("w:val"), str(int(size.pt * 2)))
        rPr.append(sz)

    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")  # standard Word hyperlink blue
    rPr.append(color)

    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)

    new_run.append(rPr)

    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    new_run.append(t)

    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def _write_contact_line(paragraph, text: str, size):
    """Render a contact line like 'LinkedIn | email | phone | city | GitHub',
    turning the LinkedIn / GitHub tokens into real hyperlinks and the email
    into a mailto: link. Unknown segments render as plain text.
    """
    segments = [seg.strip() for seg in text.split("|")]
    for i, seg in enumerate(segments):
        if i > 0:
            _add_run(paragraph, " | ", size=size)
        low = seg.lower()
        if low == "linkedin":
            _add_hyperlink(paragraph, LINKEDIN_URL, seg, size=size)
        elif low == "github":
            _add_hyperlink(paragraph, GITHUB_URL, seg, size=size)
        elif "@" in seg and " " not in seg:
            _add_hyperlink(paragraph, f"mailto:{seg}", seg, size=size)
        else:
            _add_run(paragraph, seg, size=size)


def _heading_row(doc, left_text, right_text, size, bold_left=True, italic_left=False):
    p = doc.add_paragraph()
    _tight(p, space_before=4, space_after=0)
    page_width = (doc.sections[0].page_width
                  - doc.sections[0].left_margin - doc.sections[0].right_margin)
    p.paragraph_format.tab_stops.add_tab_stop(page_width, WD_TAB_ALIGNMENT.RIGHT)
    _add_run(p, left_text, bold=bold_left, italic=italic_left, size=size)
    _add_run(p, f"\t{right_text}", size=size)
    return p


def _bullet(doc, text, size, line):
    p = doc.add_paragraph()
    _tight(p, space_before=0, space_after=0, line=line)
    p.paragraph_format.left_indent = Inches(0.22)
    p.paragraph_format.first_line_indent = Inches(-0.22)
    _add_run(p, "– ", size=size)
    _add_run(p, text, size=size)
    return p


def _section_header(doc, title, size):
    p = doc.add_paragraph()
    _tight(p, space_before=6, space_after=2)
    _add_run(p, title.upper(), bold=True, size=size)
    _add_bottom_border(p)
    return p


# ───────────────────────── resume ─────────────────────────

def write_resume_docx(resume: dict, output_path: str, tightness: int = 0):
    s = _style(tightness)
    doc = Document()
    _set_margins(doc, s["margins_tb"], s["margins_tb"], s["margins_lr"], s["margins_lr"])

    # Name
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _tight(p, space_before=0, space_after=0)
    _add_run(p, resume["name"].upper(), bold=True, size=s["name"], font=NAME_FONT)

    # Contact line — LinkedIn / GitHub / email rendered as real hyperlinks
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _tight(p, space_before=0, space_after=2)
    _write_contact_line(p, resume["contact_line"], size=s["contact"])

    # Professional summary
    _section_header(doc, "Professional Summary", s["section"])
    p = doc.add_paragraph()
    _tight(p, space_before=2, space_after=0, line=s["line"])
    _add_run(p, resume["professional_summary"], size=s["body"])

    # Work experience
    _section_header(doc, "Work Experience", s["section"])
    for job in resume.get("work_experience", []):
        left = f"{job['company']}, {job.get('location', '')}".rstrip(", ")
        _heading_row(doc, left, job.get("dates", ""), size=s["company"], bold_left=True)
        p = doc.add_paragraph()
        _tight(p, space_before=0, space_after=2)
        _add_run(p, job.get("role", ""), italic=True, size=s["role"])
        for bullet in job.get("bullets", []):
            _bullet(doc, bullet, size=s["body"], line=s["line"])

    # Education
    _section_header(doc, "Education", s["section"])
    for ed in resume.get("education", []):
        left = f"{ed['school']}, {ed.get('location', '')}".rstrip(", ")
        _heading_row(doc, left, ed.get("dates", ""), size=s["company"], bold_left=True)
        for key in ("degree_line", "courses", "research"):
            val = ed.get(key)
            if not val:
                continue
            p = doc.add_paragraph()
            _tight(p, space_before=0, space_after=0, line=s["line"])
            italic = key == "courses"
            _add_run(p, val, italic=italic, size=s["body"])

    # Skills
    _section_header(doc, "Skills", s["section"])
    for label, items in resume.get("skills", {}).items():
        p = doc.add_paragraph()
        _tight(p, space_before=0, space_after=0, line=s["line"])
        _add_run(p, f"{label}: ", bold=True, size=s["body"])
        _add_run(p, items, size=s["body"])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)


# ───────────────────────── cover letter ─────────────────────────

def write_cover_letter_docx(cover_letter_text: str, output_path: str, tightness: int = 0):
    t = max(0, min(4, int(tightness)))
    margins = [1.0, 0.85, 0.75, 0.65, 0.55][t]
    size = Pt([11.0, 10.5, 10.0, 10.0, 9.5][t])
    line = [1.15, 1.12, 1.08, 1.04, 1.0][t]
    space_after = [8, 6, 5, 4, 3][t]

    doc = Document()
    _set_margins(doc, margins, margins, margins, margins)

    paragraphs = [p.strip() for p in cover_letter_text.split("\n\n") if p.strip()]
    for para in paragraphs:
        p = doc.add_paragraph()
        _tight(p, space_before=0, space_after=space_after, line=line)
        lines = para.split("\n")
        for i, ln in enumerate(lines):
            if i > 0:
                p.add_run().add_break()
            _add_run(p, ln, size=size)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)


# ───────────────────────── PDF conversion + page counting ──────────

def convert_to_pdf(docx_path: str, pdf_path: str):
    """Convert via docx2pdf in a fresh subprocess (avoids Flask COM issues)."""
    import subprocess
    import sys

    scripts_dir = os.path.dirname(sys.executable)
    exe = os.path.join(scripts_dir, "docx2pdf.exe")
    if not os.path.exists(exe):
        exe = "docx2pdf"

    result = subprocess.run(
        [exe, docx_path, pdf_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0 or not os.path.exists(pdf_path):
        detail = (result.stderr or result.stdout or "no output").strip().splitlines()[-5:]
        raise RuntimeError(
            f"docx2pdf failed (rc={result.returncode}): {' | '.join(detail)}"
        )


def pdf_page_count(pdf_path: str) -> int:
    from pypdf import PdfReader
    return len(PdfReader(pdf_path).pages)
