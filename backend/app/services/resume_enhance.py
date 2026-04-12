"""AI-assisted profile summary from structured resume fields (no JD)."""
from __future__ import annotations

import json
from typing import Any

from app.config import settings


def _brief_for_summary(resume_json: dict[str, Any]) -> dict[str, Any]:
    c = resume_json.get("contact") or {}
    exps = resume_json.get("experience") or []
    roles = []
    for e in exps[:6]:
        if not isinstance(e, dict):
            continue
        roles.append(
            {
                "title": (e.get("title") or "")[:120],
                "company": (e.get("company") or "")[:120],
            }
        )
    edu = []
    for e in (resume_json.get("education") or [])[:4]:
        if not isinstance(e, dict):
            continue
        edu.append(
            {
                "degree": (e.get("degree") or "")[:120],
                "institution": (e.get("institution") or "")[:120],
            }
        )
    sk = resume_json.get("skills") or {}
    tech = (sk.get("technical") or [])[:24] if isinstance(sk, dict) else []
    return {
        "name": (c.get("name") or "")[:80],
        "education": edu,
        "roles": roles,
        "technical_skills": [str(x) for x in tech if str(x).strip()],
    }


async def generate_profile_summary_from_fields(resume_json: dict[str, Any]) -> str:
    """2–3 professional lines from structured data only; no employers or degrees not in the payload."""
    if not (settings.openai_api_key or "").strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    brief = _brief_for_summary(resume_json)
    sys = (
        "Write exactly 2 or 3 short sentences for a resume Summary / Objective. "
        "Use ONLY facts present in the JSON — never invent employers, schools, or job titles. "
        "No bullet points, no contact details, no URLs. Professional tone."
    )
    user = json.dumps(brief, ensure_ascii=False)
    resp = await client.chat.completions.create(
        model=settings.openai_parse_model,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0.35,
        max_tokens=200,
    )
    text = (resp.choices[0].message.content or "").strip()
    return text[:1200]
