from io import BytesIO
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Inches, Pt

from .template_pdf_export import (
    DEFAULT_LINKEDIN_URL,
    DEFAULT_PORTFOLIO_URL,
    _parse_resume,
)


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip()
    if not cleaned:
        cleaned = "optimized_resume"
    return f"{cleaned}.docx"


def _add_hyperlink(paragraph, text: str, url: str) -> None:
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")

    color = OxmlElement("w:color")
    color.set(qn("w:val"), "000000")
    r_pr.append(color)

    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    r_pr.append(underline)

    new_run.append(r_pr)
    text_elem = OxmlElement("w:t")
    text_elem.text = text
    new_run.append(text_elem)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def _add_contact_line(document: Document, contact_html: str) -> None:
    plain = re.sub(r"<[^>]+>", "", contact_html).strip()
    parts = [p.strip() for p in plain.split("|") if p.strip()]

    # de-duplicate while preserving order
    seen = set()
    ordered = []
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(part)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(5)

    for idx, part in enumerate(ordered):
        low = part.lower()
        if idx > 0:
            p.add_run(" | ")

        if "@" in part and "http" not in low:
            _add_hyperlink(p, part, f"mailto:{part}")
        elif "linkedin" in low:
            _add_hyperlink(p, "LinkedIn", DEFAULT_LINKEDIN_URL)
        elif "portfolio" in low or "github.io" in low:
            _add_hyperlink(p, "Portfolio", DEFAULT_PORTFOLIO_URL)
        elif low.startswith("http://") or low.startswith("https://"):
            _add_hyperlink(p, part, part)
        else:
            p.add_run(part)

    for run in p.runs:
        run.font.size = Pt(10)


def _add_section_title(document: Document, text: str) -> None:
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(13)


def _add_role_block(document: Document, role: str, date: str, org: str, location: str) -> None:
    table = document.add_table(rows=2, cols=2)
    table.autofit = False
    table.columns[0].width = Inches(4.7)
    table.columns[1].width = Inches(2.0)

    left_top = table.cell(0, 0).paragraphs[0]
    left_top.paragraph_format.space_after = Pt(0)
    lt = left_top.add_run(role)
    lt.bold = True
    lt.font.size = Pt(11.5)

    right_top = table.cell(0, 1).paragraphs[0]
    right_top.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_top.paragraph_format.space_after = Pt(0)
    rt = right_top.add_run(date)
    rt.font.size = Pt(11)

    left_bottom = table.cell(1, 0).paragraphs[0]
    left_bottom.paragraph_format.space_after = Pt(0)
    lb = left_bottom.add_run(org)
    lb.italic = True
    lb.font.size = Pt(11)

    right_bottom = table.cell(1, 1).paragraphs[0]
    right_bottom.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_bottom.paragraph_format.space_after = Pt(0)
    rb = right_bottom.add_run(location)
    rb.font.size = Pt(11)


def _compact_context(context: dict) -> dict:
    ctx = {
        "header": dict(context.get("header", {})),
        "summary_keywords": (context.get("summary_keywords") or "")[:260].strip(),
        "summary": (context.get("summary") or "")[:620].strip(),
        "core_competencies": list(context.get("core_competencies", []))[:7],
        "technologies": context.get("technologies", ""),
        "technical_skills": context.get("technical_skills", ""),
        "experiences": [],
        "education_entries": list(context.get("education_entries", []))[:3],
        "honors": list(context.get("honors", []))[:3],
        "extras": [],
    }

    for exp in context.get("experiences", []):
        ctx["experiences"].append(
            {
                "role": exp.get("role", ""),
                "date": exp.get("date", ""),
                "org": exp.get("org", ""),
                "location": exp.get("location", ""),
                "bullets": list(exp.get("bullets", []))[:4],
            }
        )

    # Remove duplicated tools line if technical skills already has same words.
    if ctx["technical_skills"] and ctx["technologies"]:
        tech_set = set(re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]+", ctx["technical_skills"].lower()))
        if len(tech_set) > 3:
            filtered = []
            for c in ctx["core_competencies"]:
                low = c.lower()
                if low.startswith("tools:"):
                    continue
                filtered.append(c)
            ctx["core_competencies"] = filtered

    return ctx


def build_resume_docx(resume_text: str, filename: str = "optimized_resume") -> tuple[bytes, str]:
    if len(resume_text.strip()) < 20:
        raise ValueError("Resume text is too short to export.")

    base = _parse_resume(resume_text)
    context = _compact_context(base)

    document = Document()

    # Compact page setup for 2-page target.
    section = document.sections[0]
    section.top_margin = Inches(0.45)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(11)

    header = context.get("header", {})

    if header.get("name"):
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(header["name"])
        run.bold = True
        run.font.size = Pt(24)

    if header.get("contact_html"):
        _add_contact_line(document, header.get("contact_html", ""))

    if header.get("headline"):
        p = document.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        h = p.add_run(header["headline"])
        h.bold = True
        h.font.size = Pt(14)

    if context.get("summary_keywords"):
        p = document.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        k = p.add_run(context["summary_keywords"])
        k.bold = True
        k.font.size = Pt(11)

    if context.get("summary"):
        p = document.add_paragraph(context["summary"])
        p.paragraph_format.space_after = Pt(3)

    core = context.get("core_competencies", [])
    if core:
        _add_section_title(document, "Core Competencies")
        for item in core:
            p = document.add_paragraph(item, style="List Bullet")
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)

    if context.get("technologies"):
        _add_section_title(document, "Technologies")
        p = document.add_paragraph()
        t1 = p.add_run("Technologies: ")
        t1.bold = True
        t2 = p.add_run(context["technologies"])
        t2.bold = False
        p.paragraph_format.space_after = Pt(2)

    tech_skills = context.get("technical_skills", "")
    if tech_skills:
        _add_section_title(document, "Technical Skills")
        p = document.add_paragraph(tech_skills)
        p.paragraph_format.space_after = Pt(2)

    experiences = context.get("experiences", [])
    if experiences:
        _add_section_title(document, "Professional Experience")
        for exp in experiences:
            _add_role_block(
                document,
                exp.get("role", ""),
                exp.get("date", ""),
                exp.get("org", ""),
                exp.get("location", ""),
            )
            for bullet in exp.get("bullets", []):
                p = document.add_paragraph(bullet, style="List Bullet")
                p.paragraph_format.left_indent = Inches(0.05)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.space_before = Pt(0)
            spacer = document.add_paragraph()
            spacer.paragraph_format.space_after = Pt(2)

    education = context.get("education_entries", [])
    if education:
        _add_section_title(document, "Education")
        for edu in education:
            table = document.add_table(rows=2, cols=2)
            table.autofit = False
            table.columns[0].width = Inches(4.7)
            table.columns[1].width = Inches(2.0)

            l1 = table.cell(0, 0).paragraphs[0]
            l1.paragraph_format.space_after = Pt(0)
            r1 = l1.add_run(edu.get("degree", ""))
            r1.bold = True
            r1.font.size = Pt(11)

            d1 = table.cell(0, 1).paragraphs[0]
            d1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            d1.paragraph_format.space_after = Pt(0)
            d1r = d1.add_run(edu.get("date", ""))
            d1r.font.size = Pt(11)

            l2 = table.cell(1, 0).paragraphs[0]
            l2.paragraph_format.space_after = Pt(0)
            s2 = l2.add_run(edu.get("school", ""))
            s2.italic = True
            s2.font.size = Pt(10.5)

            table.cell(1, 1).paragraphs[0].paragraph_format.space_after = Pt(0)

            if edu.get("gpa"):
                gp = document.add_paragraph(edu.get("gpa", ""))
                gp.paragraph_format.space_after = Pt(1)
                gp.runs[0].font.size = Pt(10.5)

    honors = context.get("honors", [])
    if honors:
        _add_section_title(document, "Honors & Recognition")
        for item in honors:
            p = document.add_paragraph(item, style="List Bullet")
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)

    output = BytesIO()
    document.save(output)
    output.seek(0)
    return output.read(), _safe_filename(filename)
