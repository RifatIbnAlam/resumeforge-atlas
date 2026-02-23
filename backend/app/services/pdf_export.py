import re
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DEFAULT_LINKEDIN_URL = "https://www.linkedin.com/in/rifat-ibn-alam/"
DEFAULT_PORTFOLIO_URL = "https://rifatibnalam.github.io/Rifat-Portfolio/"


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip()
    if not cleaned:
        cleaned = "optimized_resume"
    return f"{cleaned}.pdf"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _parse_resume_text(resume_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in resume_text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return {"name": "", "contact": "", "title": "", "sections": {}}

    name = lines[0]
    contact = lines[1] if len(lines) > 1 else ""
    title = lines[2] if len(lines) > 2 and ":" not in lines[2] else ""

    start_idx = 3 if title else 2
    sections: dict[str, list[str]] = {}
    current = "General"
    sections[current] = []

    for line in lines[start_idx:]:
        is_colon_heading = line.endswith(":") and len(line) < 60
        is_upper_heading = (
            len(line) < 60
            and line.upper() == line
            and any(ch.isalpha() for ch in line)
            and "|" not in line
            and not line.startswith("-")
        )
        if is_colon_heading or is_upper_heading:
            current = line[:-1].strip()
            if is_upper_heading and not is_colon_heading:
                current = line.strip().title()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return {"name": name, "contact": contact, "title": title, "sections": sections}


def _contact_markup(contact_line: str) -> str:
    pieces = [p.strip() for p in contact_line.split("|") if p.strip()]
    if not pieces:
        return _escape(contact_line)

    out: list[str] = []
    for piece in pieces:
        p = piece.strip()
        low = p.lower()
        if "@" in p and "http" not in low:
            out.append(f'<link href="mailto:{_escape(p)}"><u>{_escape(p)}</u></link>')
            continue
        if "linkedin.com" in low or low == "linkedin":
            out.append(f'<link href="{DEFAULT_LINKEDIN_URL}"><u>LinkedIn</u></link>')
            continue
        if "portfolio" in low or "github.io" in low:
            out.append(f'<link href="{DEFAULT_PORTFOLIO_URL}"><u>Portfolio</u></link>')
            continue
        if low.startswith("http://") or low.startswith("https://"):
            out.append(f'<link href="{_escape(p)}"><u>{_escape(p)}</u></link>')
            continue
        out.append(_escape(p))
    return " | ".join(out)


def _header(styles: dict[str, ParagraphStyle], story: list[Any], title: str) -> None:
    story.append(Spacer(1, 0.08 * inch))
    story.append(HRFlowable(color=colors.HexColor("#BBBBBB"), thickness=0.8))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(_escape(title.upper()), styles["section_title"]))
    story.append(Spacer(1, 0.08 * inch))


def _add_professional_experience(
    styles: dict[str, ParagraphStyle], story: list[Any], lines: list[str]
) -> None:
    def looks_like_date(value: str) -> bool:
        return bool(
            re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–-]\s*(Present|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                value,
                flags=re.IGNORECASE,
            )
        )

    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and not line.startswith("-"):
            parts = [part.strip() for part in line.split("|")]
            role = parts[0] if parts else ""
            org = ""
            location = ""
            date = ""

            if len(parts) >= 4:
                org = parts[1]
                location = parts[2]
                date = parts[3]
            elif len(parts) == 3:
                org = parts[1]
                if looks_like_date(parts[2]):
                    date = parts[2]
                else:
                    location = parts[2]
            elif len(parts) == 2:
                org = parts[1]

            if i + 1 < len(lines) and not lines[i + 1].startswith("-") and "|" not in lines[i + 1]:
                if not date and looks_like_date(lines[i + 1]):
                    date = lines[i + 1]
                    i += 1

            left_title = f"<b>{_escape(role)}</b>"
            left_sub = _escape(org + (f" | {location}" if location else ""))
            left = Paragraph(f"{left_title}<br/><i>{left_sub}</i>", styles["entry_left"])
            right = Paragraph(_escape(date), styles["entry_right"])

            table = Table([[left, right]], colWidths=[4.6 * inch, 1.9 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 0.08 * inch))
            i += 1
            while i < len(lines) and lines[i].startswith("-"):
                bullet = re.sub(r"^-+\s*", "", lines[i])
                story.append(Paragraph(f"&bull;&nbsp;&nbsp;{_escape(bullet)}", styles["body"]))
                i += 1
            story.append(Spacer(1, 0.1 * inch))
            continue

        if line.startswith("-"):
            bullet = re.sub(r"^-+\s*", "", line)
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{_escape(bullet)}", styles["body"]))
        else:
            story.append(Paragraph(_escape(line), styles["body"]))
        i += 1


def _add_education(styles: dict[str, ParagraphStyle], story: list[Any], lines: list[str]) -> None:
    entry_starts = ("master", "bachelor", "phd", "doctor", "associate", "b.s", "m.s", "mba")
    merged: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        lowered = stripped.lower()
        if lowered.startswith("gpa") and merged:
            merged[-1] = f"{merged[-1]} | {stripped}"
            continue

        is_new_entry = ("|" in stripped and lowered.startswith(entry_starts))
        if is_new_entry:
            merged.append(stripped)
            continue

        if merged:
            merged[-1] = f"{merged[-1]} {stripped}"
        else:
            merged.append(stripped)

    for entry in merged:
        story.append(Paragraph(_escape(entry), styles["body"]))
    story.append(Spacer(1, 0.06 * inch))


def build_resume_pdf(resume_text: str, filename: str = "optimized_resume") -> tuple[bytes, str]:
    if len(resume_text.strip()) < 20:
        raise ValueError("Resume text is too short to export.")

    parsed = _parse_resume_text(resume_text)
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Optimized Resume",
    )

    styles = getSampleStyleSheet()
    custom = {
        "name": ParagraphStyle(
            "name",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=24,
            leading=26,
            alignment=1,
            spaceAfter=6,
        ),
        "contact": ParagraphStyle(
            "contact",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=14,
            alignment=1,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "title",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=13,
            leading=15,
            spaceAfter=8,
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=13,
            leading=15,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=15,
            spaceAfter=4,
        ),
        "entry_left": ParagraphStyle(
            "entry_left",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=15,
        ),
        "entry_right": ParagraphStyle(
            "entry_right",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=15,
        ),
    }

    story: list[Any] = []
    story.append(Paragraph(_escape(parsed["name"]), custom["name"]))
    if parsed["contact"]:
        story.append(Paragraph(_contact_markup(parsed["contact"]), custom["contact"]))
    story.append(Spacer(1, 0.06 * inch))
    story.append(HRFlowable(color=colors.HexColor("#BBBBBB"), thickness=0.8))
    story.append(Spacer(1, 0.08 * inch))

    if parsed["title"]:
        story.append(Paragraph(_escape(parsed["title"].upper()), custom["title"]))
        story.append(Spacer(1, 0.06 * inch))

    section_order = [
        "General",
        "Summary",
        "Core Competencies",
        "Technologies",
        "Technical Skills",
        "Professional Experience",
        "Education",
        "Certifications & Training",
        "Additional Information",
        "Honors",
    ]

    for section_name in section_order:
        lines = parsed["sections"].get(section_name)
        if not lines:
            continue
        if section_name != "General":
            _header(custom, story, section_name)
        else:
            story.append(Spacer(1, 0.08 * inch))
        if section_name == "Professional Experience":
            _add_professional_experience(custom, story, lines)
        elif section_name == "Education":
            _add_education(custom, story, lines)
        else:
            for line in lines:
                if line.startswith("-"):
                    bullet = re.sub(r"^-+\s*", "", line)
                    story.append(Paragraph(f"&bull;&nbsp;&nbsp;{_escape(bullet)}", custom["body"]))
                else:
                    story.append(Paragraph(_escape(line), custom["body"]))
            story.append(Spacer(1, 0.06 * inch))

    extra_sections = [
        name for name in parsed["sections"].keys() if name not in section_order and name != "General"
    ]
    for section_name in extra_sections:
        lines = parsed["sections"].get(section_name) or []
        if not lines:
            continue
        _header(custom, story, section_name)
        for line in lines:
            if line.startswith("-"):
                bullet = re.sub(r"^-+\s*", "", line)
                story.append(Paragraph(f"&bull;&nbsp;&nbsp;{_escape(bullet)}", custom["body"]))
            else:
                story.append(Paragraph(_escape(line), custom["body"]))
        story.append(Spacer(1, 0.06 * inch))

    doc.build(story)
    output.seek(0)
    return output.read(), _safe_filename(filename)
