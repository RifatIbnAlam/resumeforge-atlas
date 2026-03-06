from .fallback import fallback_optimize_resume
from .keyword import coverage_report, extract_keywords
from .llm_client import call_optimizer_llm


def _extract_date_ranges(text: str) -> list[str]:
    import re

    pattern = re.compile(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–-]\s*(?:Present|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
        flags=re.IGNORECASE,
    )
    return pattern.findall(text)


def _extract_experience_section(text: str) -> str:
    lines = text.splitlines()
    in_experience = False
    collected: list[str] = []

    stop_headings = {
        "education",
        "technical skills",
        "technologies",
        "honors",
        "honors & recognition",
        "certifications & training",
        "additional information",
        "summary",
        "core competencies",
    }

    for raw in lines:
        line = raw.strip()
        lower = line.lower().rstrip(":")
        if lower == "professional experience":
            in_experience = True
            continue
        if in_experience and lower in stop_headings:
            break
        if in_experience:
            collected.append(raw)

    return "\n".join(collected)


def _ensure_experience_dates(optimized_text: str, original_text: str) -> str:
    import re

    optimized_experience = _extract_experience_section(optimized_text)
    original_experience = _extract_experience_section(original_text)

    if _extract_date_ranges(optimized_experience):
        return optimized_text

    date_ranges = _extract_date_ranges(original_experience)
    if not date_ranges:
        return optimized_text

    lines = optimized_text.splitlines()
    in_experience = False
    idx = 0

    role_keywords = (
        "coordinator",
        "engineer",
        "lecturer",
        "intern",
        "manager",
        "analyst",
        "developer",
        "specialist",
        "lead",
    )

    month_pat = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.IGNORECASE)

    for i, raw in enumerate(lines):
        line = raw.strip()
        lower = line.lower().rstrip(":")
        if lower == "professional experience":
            in_experience = True
            continue
        if in_experience and lower in {
            "education",
            "technical skills",
            "technologies",
            "honors",
            "honors & recognition",
            "certifications & training",
            "additional information",
        }:
            in_experience = False

        if not in_experience:
            continue
        if not line or line.startswith("-") or line.startswith("•"):
            continue
        if month_pat.search(line):
            continue
        if "|" in line:
            continue

        role_like = any(k in line.lower() for k in role_keywords)
        if not role_like or idx >= len(date_ranges):
            continue

        lines[i] = f"{line} | {date_ranges[idx]}"
        idx += 1

    return "\n".join(lines)


def _dedupe_resume_text(text: str) -> str:
    lines = text.splitlines()
    has_technical_skills = any(
        line.strip().lower().rstrip(":") == "technical skills" for line in lines
    )
    if not has_technical_skills:
        return text

    normalized: list[str] = []
    current_section = ""
    for raw in lines:
        stripped = raw.strip()
        heading_candidate = stripped.lower().rstrip(":")
        if heading_candidate in {
            "summary",
            "core competencies",
            "technical skills",
            "professional experience",
            "education",
            "certifications & training",
            "additional information",
            "honors",
        }:
            current_section = heading_candidate

        if current_section == "core competencies":
            cleaned = stripped.lstrip("-").lstrip("•").strip().lower()
            if cleaned.startswith("tools:"):
                continue

        normalized.append(raw)

    return "\n".join(normalized).strip()


def _ensure_headline_summary_break(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    split_markers = (
        " results-oriented ",
        " experienced ",
        " skilled ",
        " proven ",
        " detail-oriented ",
        " strategic ",
    )

    out: list[str] = []
    for line in lines:
        raw = line.rstrip()
        low = f" {raw.lower()} "
        if "•" in raw:
            split_at = -1
            for marker in split_markers:
                idx = low.find(marker)
                if idx > 0:
                    split_at = idx
                    break
            if split_at > 0:
                left = raw[:split_at].rstrip(" •")
                right = raw[split_at:].strip()
                out.append(left)
                out.append("")
                out.append(right)
                continue
        out.append(raw)

    fixed: list[str] = []
    for i, line in enumerate(out):
        fixed.append(line)
        if (
            i + 1 < len(out)
            and "•" in line
            and out[i + 1].strip()
            and not out[i + 1].strip().endswith(":")
            and out[i + 1].strip().upper() != out[i + 1].strip()
        ):
            fixed.append("")

    return "\n".join(fixed).strip()


def optimize_resume(resume_text: str, job_description: str) -> dict:
    resume_text = resume_text.strip()
    job_description = job_description.strip()

    if len(resume_text) < 20 or len(job_description) < 20:
        raise ValueError("Resume and job description must each be at least 20 characters")

    keywords = extract_keywords(job_description)
    report = coverage_report(resume_text, keywords)

    try:
        llm_result = call_optimizer_llm(resume_text, job_description)
        mode = "llm"
    except Exception as err:
        reason = f"{type(err).__name__}: {str(err)}".strip()
        fallback = fallback_optimize_resume(resume_text, report, reason=reason[:240])
        return {
            "optimized_resume": fallback["optimized_resume"],
            "summary": fallback["summary"],
            "keyword_report": report,
            "warnings": fallback["warnings"],
            "mode": fallback["mode"],
        }

    optimized_resume = _dedupe_resume_text(llm_result["optimized_resume"])
    optimized_resume = _ensure_experience_dates(optimized_resume, resume_text)
    optimized_resume = _ensure_headline_summary_break(optimized_resume)

    return {
        "optimized_resume": optimized_resume,
        "summary": llm_result["summary"],
        "keyword_report": report,
        "warnings": llm_result.get("warnings", []),
        "mode": mode,
    }
