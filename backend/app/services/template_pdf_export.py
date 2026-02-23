import os
import re
import tempfile
from html import escape
from pathlib import Path
from typing import Optional
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

DEFAULT_LINKEDIN_URL = "https://www.linkedin.com/in/rifat-ibn-alam/"
DEFAULT_PORTFOLIO_URL = "https://rifatibnalam.github.io/Rifat-Portfolio/"

SECTION_KEYS = {
    "summary": "summary",
    "core competencies": "core_competencies",
    "technologies": "technologies",
    "technical skills": "technical_skills",
    "professional experience": "professional_experience",
    "education": "education",
    "honors": "honors",
    "honors & recognition": "honors",
}

DATE_PAT = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–-]\s*(?:Present|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
    flags=re.IGNORECASE,
)
MONTH_YEAR_PAT = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
    flags=re.IGNORECASE,
)
DEGREE_START_PAT = re.compile(
    r"^(master|bachelor|phd|doctor|associate|mba|m\\.s|b\\.s)",
    flags=re.IGNORECASE,
)


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip()
    if not cleaned:
        cleaned = "optimized_resume"
    return f"{cleaned}.pdf"


def _normalize_heading(line: str) -> Optional[str]:
    raw = line.strip().rstrip(":")
    lower = raw.lower()
    if lower in SECTION_KEYS:
        return SECTION_KEYS[lower]

    if (
        len(raw) <= 60
        and raw.upper() == raw
        and any(c.isalpha() for c in raw)
        and "|" not in raw
        and not raw.startswith("-")
    ):
        lower = raw.lower()
        return SECTION_KEYS.get(lower)

    return None


def _contact_html(contact_line: str) -> str:
    parts = [p.strip() for p in contact_line.split("|") if p.strip()]
    output: list[str] = []

    for part in parts:
        low = part.lower()
        if "@" in part and "http" not in low:
            output.append(f'<a href="mailto:{escape(part)}">{escape(part)}</a>')
        elif "linkedin.com" in low or low == "linkedin":
            output.append(f'<a href="{DEFAULT_LINKEDIN_URL}">LinkedIn</a>')
        elif "portfolio" in low or "github.io" in low:
            output.append(f'<a href="{DEFAULT_PORTFOLIO_URL}">Portfolio</a>')
        elif low.startswith("http://") or low.startswith("https://"):
            output.append(f'<a href="{escape(part)}">{escape(part)}</a>')
        else:
            output.append(escape(part))

    return " | ".join(output)


def _parse_resume(resume_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Resume text is too short to export.")

    name = lines[0]
    contact = lines[1]
    headline = ""
    idx = 2

    if idx < len(lines) and ":" not in lines[idx]:
        heading_candidate = _normalize_heading(lines[idx])
        if heading_candidate is None:
            headline = lines[idx]
            idx += 1

    sections: dict[str, list[str]] = {"general": []}
    current = "general"

    for line in lines[idx:]:
        key = _normalize_heading(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    summary = " ".join(sections.get("summary", [])).strip()

    core_competencies_raw = [
        re.sub(r"^[\-•]\s*", "", v).strip()
        for v in sections.get("core_competencies", [])
        if v.strip()
    ]

    technical_skills = " ".join(sections.get("technical_skills", [])).strip()
    technologies = " ".join(sections.get("technologies", [])).strip()
    if technologies.lower().startswith("technologies:"):
        technologies = technologies.split(":", 1)[1].strip()

    core_competencies: list[str] = []
    for item in core_competencies_raw:
        if item.lower().startswith("technologies:"):
            if not technologies:
                technologies = item.split(":", 1)[1].strip()
            continue
        if item.lower().startswith("tools:") and technical_skills:
            continue
        core_competencies.append(item)

    experiences = _parse_experience_entries(sections.get("professional_experience", []))
    education_entries = _parse_education_entries(sections.get("education", []))

    honors = [
        re.sub(r"^[\-•]\s*", "", v).strip()
        for v in sections.get("honors", [])
        if v.strip()
    ]

    extra_sections = []
    for k, v in sections.items():
        if k in {
            "general",
            "summary",
            "core_competencies",
            "technologies",
            "technical_skills",
            "professional_experience",
            "education",
            "honors",
        }:
            continue
        if not v:
            continue
        extra_sections.append(
            {
                "title": k.replace("_", " ").title(),
                "lines": [re.sub(r"^[\-•]\s*", "", x).strip() for x in v if x.strip()],
            }
        )

    if not summary and sections.get("general"):
        summary = " ".join(sections["general"][:4]).strip()

    headline, summary = _split_headline_summary(headline, summary)

    return {
        "header": {
            "name": name,
            "contact_html": _contact_html(contact),
            "headline": headline,
        },
        "summary": summary,
        "core_competencies": core_competencies,
        "technologies": technologies,
        "technical_skills": technical_skills,
        "experiences": experiences,
        "education_entries": education_entries,
        "honors": honors,
        "extras": extra_sections,
    }


def _split_headline_summary(headline: str, summary: str) -> tuple[str, str]:
    if not headline:
        return headline, summary
    if summary:
        return headline.strip(), summary.strip()
    if "•" not in headline:
        return headline.strip(), summary

    # If a long keyword line accidentally includes a sentence, split it.
    markers = [
        " Results-oriented ",
        " Experienced ",
        " Skilled ",
        " Proven ",
        " Strategic ",
        " Detail-oriented ",
    ]
    split_at = -1
    for marker in markers:
        idx = headline.find(marker)
        if idx > 0:
            split_at = idx
            break

    if split_at > 0:
        new_headline = headline[:split_at].strip(" •")
        new_summary = headline[split_at:].strip()
        return new_headline, new_summary

    # Fallback split for long trailing segment.
    segments = [s.strip() for s in headline.split("•") if s.strip()]
    if len(segments) >= 2 and len(segments[-1]) > 80:
        last = segments[-1]
        for token in [" with ", " who ", " having "]:
            pos = last.lower().find(token)
            if pos > 20:
                new_headline = " • ".join(segments[:-1] + [last[:pos].strip()])
                new_summary = last[pos:].strip()
                return new_headline.strip(), new_summary

    return headline.strip(), summary


def _split_org_location(text: str) -> tuple[str, str]:
    if " | " in text:
        parts = [p.strip() for p in text.split("|", 1)]
        return parts[0], parts[1] if len(parts) > 1 else ""
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) >= 3:
            return ", ".join(parts[:-2]).strip(), ", ".join(parts[-2:]).strip()
        if len(parts) == 2:
            return parts[0], parts[1]
    return text.strip(), ""


def _parse_role_line(line: str) -> dict[str, str]:
    role = line.strip()
    org = ""
    location = ""
    date = ""

    parts = [p.strip() for p in line.split("|")] if "|" in line else []
    if parts:
        role = parts[0]
        for part in parts[1:]:
            if DATE_PAT.search(part):
                date = DATE_PAT.search(part).group(0)
            elif not org:
                org = part
            elif not location:
                location = part
    else:
        match = DATE_PAT.search(line)
        if match:
            date = match.group(0)
            role = (line[: match.start()] + line[match.end() :]).strip(" |-")

    return {"role": role.strip(), "org": org.strip(), "location": location.strip(), "date": date.strip()}


def _looks_like_org_line(text: str) -> bool:
    low = text.lower()
    markers = ("university", "institute", "school", "center", "bangladesh", "utah", "company", "tobacco")
    return any(m in low for m in markers)


def _looks_like_role_line(text: str) -> bool:
    low = text.lower()
    markers = ("coordinator", "engineer", "lecturer", "manager", "analyst", "intern", "developer", "specialist", "lead")
    return any(re.search(rf"\b{re.escape(m)}\b", low) for m in markers)


def _parse_experience_entries(lines: list[str]) -> list[dict[str, Any]]:
    def clean_bullet(text: str) -> str:
        value = text.strip()
        while True:
            new_value = re.sub(r"^\s*(?:[•\-]\s*)+", "", value)
            if new_value == value:
                break
            value = new_value
        return value

    entries: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None

    clean_lines = [l.strip() for l in lines if l and l.strip()]
    i = 0
    while i < len(clean_lines):
        line = clean_lines[i]

        if line.startswith("-") or line.startswith("•"):
            if current is not None:
                current["bullets"].append(clean_bullet(line))
            i += 1
            continue

        # Wrapped lines inside bullet points should remain in the same bullet.
        if current is not None and not _looks_like_role_line(line):
            date_match = DATE_PAT.search(line)
            if date_match and not current.get("date"):
                current["date"] = date_match.group(0).strip()
                i += 1
                continue
            if current.get("bullets"):
                current["bullets"][-1] = f"{current['bullets'][-1]} {line}".strip()
                i += 1
                continue

        if current is not None and not current.get("org") and _looks_like_org_line(line) and not _looks_like_role_line(line):
            org, location = _split_org_location(line)
            current["org"] = org
            current["location"] = location
            i += 1
            continue

        parsed = _parse_role_line(line)
        # Guard: if parser couldn't identify a role-like start, treat as continuation text.
        if current is not None and not _looks_like_role_line(parsed["role"]):
            if current.get("bullets"):
                current["bullets"][-1] = f"{current['bullets'][-1]} {line}".strip()
            elif not current.get("org"):
                org, location = _split_org_location(line)
                current["org"] = org
                current["location"] = location
            i += 1
            continue

        current = {
            "role": parsed["role"],
            "org": parsed["org"],
            "location": parsed["location"],
            "date": parsed["date"],
            "bullets": [],
        }

        if i + 1 < len(clean_lines):
            nxt = clean_lines[i + 1]
            if (not nxt.startswith(("-", "•")) and not _looks_like_role_line(nxt) and _looks_like_org_line(nxt) and not current["org"]):
                nxt_no_date = DATE_PAT.sub("", nxt).strip(" |-")
                org, location = _split_org_location(nxt_no_date)
                current["org"] = org
                current["location"] = location
                if not current.get("date"):
                    m = DATE_PAT.search(nxt)
                    if m:
                        current["date"] = m.group(0).strip()
                i += 1

        if i + 1 < len(clean_lines) and not current.get("date"):
            nxt = clean_lines[i + 1]
            if DATE_PAT.search(nxt) and not _looks_like_role_line(nxt):
                current["date"] = DATE_PAT.search(nxt).group(0).strip()
                i += 1

        entries.append(current)
        i += 1

    return entries


def _parse_education_entries(lines: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: Optional[dict[str, str]] = None

    def parse_edu_line(line: str) -> dict[str, str]:
        entry = {"degree": "", "date": "", "school": "", "gpa": ""}
        working = line.strip()

        gpa_match = re.search(r"GPA:\s*[0-9.]+", working, flags=re.IGNORECASE)
        if gpa_match:
            entry["gpa"] = gpa_match.group(0).strip()
            working = (working[: gpa_match.start()] + " " + working[gpa_match.end() :]).strip()

        date_match = DATE_PAT.search(working) or MONTH_YEAR_PAT.search(working)
        if date_match:
            entry["date"] = date_match.group(0).strip()
            working = (working[: date_match.start()] + " " + working[date_match.end() :]).strip()

        parts = [p.strip() for p in working.split("|") if p.strip()]
        if parts:
            entry["degree"] = parts[0]
            if len(parts) > 1:
                entry["school"] = " | ".join(parts[1:])
        else:
            entry["degree"] = working

        return entry

    for raw in [l.strip() for l in lines if l and l.strip()]:
        line = re.sub(r"^[\\-•]\\s*", "", raw).strip()
        lower = line.lower()

        if DEGREE_START_PAT.search(line):
            if current:
                entries.append(current)
            current = parse_edu_line(line)
            continue

        if current is None:
            continue

        if lower.startswith("gpa"):
            current["gpa"] = line
        elif DATE_PAT.search(line) or MONTH_YEAR_PAT.search(line):
            current["date"] = DATE_PAT.search(line).group(0) if DATE_PAT.search(line) else MONTH_YEAR_PAT.search(line).group(0)
        else:
            # Avoid swallowing the next degree line into previous school.
            if DEGREE_START_PAT.search(line):
                entries.append(current)
                current = parse_edu_line(line)
            else:
                current["school"] = (current["school"] + " " + line).strip()

    if current:
        entries.append(current)

    return entries


def _template_env() -> Environment:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_resume_pdf_from_template(resume_text: str, filename: str = "optimized_resume") -> tuple[bytes, str]:
    if len(resume_text.strip()) < 20:
        raise ValueError("Resume text is too short to export.")

    context = _parse_resume(resume_text)
    env = _template_env()
    template = env.get_template("resume_template.html")
    html = template.render(**context)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf_path = tmp_pdf.name

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(
                path=tmp_pdf_path,
                format="Letter",
                print_background=True,
                margin={"top": "0.65in", "right": "0.75in", "bottom": "0.65in", "left": "0.75in"},
            )
            browser.close()

        with open(tmp_pdf_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        try:
            os.remove(tmp_pdf_path)
        except OSError:
            pass

    return pdf_bytes, _safe_filename(filename)
