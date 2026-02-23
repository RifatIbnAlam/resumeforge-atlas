import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from ..prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

OPENAI_API_URL = "https://api.openai.com/v1/responses"

load_dotenv()


def _extract_text_output(data: dict[str, Any]) -> str:
    direct = (data.get("output_text") or "").strip()
    if direct:
        return direct

    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            content_type = content.get("type")
            if content_type in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])

    return "\n".join(parts).strip()


def call_optimizer_llm(resume_text: str, job_description: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    prompt = USER_PROMPT_TEMPLATE.format(
        resume_text=resume_text.strip(),
        job_description=job_description.strip(),
    )

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "resume_optimization",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "optimized_resume": {"type": "string"},
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["summary", "optimized_resume", "warnings"],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(OPENAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    text_output = _extract_text_output(data)
    if not text_output:
        status = data.get("status", "unknown")
        raise RuntimeError(f"LLM returned empty response (status={status})")

    try:
        parsed = json.loads(text_output)
    except json.JSONDecodeError as err:
        preview = text_output[:300].replace("\n", " ")
        raise RuntimeError(f"LLM output was not valid JSON: {preview}") from err

    return parsed
