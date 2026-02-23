import re
from collections import Counter

STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "that",
    "this",
    "from",
    "have",
    "will",
    "your",
    "you",
    "our",
    "are",
    "job",
    "role",
    "team",
    "years",
    "year",
    "work",
    "experience",
    "required",
    "preferred",
    "ability",
    "including",
    "strong",
    "using",
    "skills",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def extract_keywords(job_description: str, limit: int = 35) -> list[str]:
    counts = Counter(_tokenize(job_description))
    keywords = [word for word, _ in counts.most_common(limit)]
    return keywords


def coverage_report(resume_text: str, keywords: list[str]) -> dict:
    resume_lower = resume_text.lower()
    present = [k for k in keywords if re.search(rf"\\b{re.escape(k)}\\b", resume_lower)]
    missing = [k for k in keywords if k not in present]

    coverage = (len(present) / len(keywords) * 100.0) if keywords else 0.0

    return {
        "required_keywords": keywords,
        "present_keywords": present,
        "missing_keywords": missing,
        "coverage_pct": round(coverage, 2),
    }
