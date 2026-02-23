from typing import Optional


def fallback_optimize_resume(
    resume_text: str, keyword_report: dict, reason: Optional[str] = None
) -> dict:
    missing_top = keyword_report["missing_keywords"][:10]
    present_top = keyword_report["present_keywords"][:10]

    summary_parts = [
        "Fallback mode used because the LLM rewrite step failed.",
        f"Detected keyword coverage: {keyword_report['coverage_pct']}%.",
    ]
    if reason:
        summary_parts.append(f"LLM error: {reason}")

    if missing_top:
        summary_parts.append(
            "Consider strengthening truthful mentions for: " + ", ".join(missing_top)
        )

    optimized_resume = (
        "[FALLBACK OUTPUT]\n\n"
        "This mode does not rewrite your resume automatically.\n"
        "Use the keyword report to manually improve your resume while keeping claims truthful.\n\n"
        "Top matched keywords: "
        + (", ".join(present_top) if present_top else "None")
        + "\n"
        "Top missing keywords: "
        + (", ".join(missing_top) if missing_top else "None")
        + "\n\n"
        "Original Resume:\n"
        + resume_text.strip()
    )

    return {
        "summary": " ".join(summary_parts),
        "optimized_resume": optimized_resume,
        "warnings": [
            "Fix the LLM error shown above, then retry.",
            "Never add unsupported skills or experiences.",
        ],
        "mode": "fallback",
    }
