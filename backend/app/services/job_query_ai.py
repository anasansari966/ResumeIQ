"""LLM + resume-only heuristics: job search queries from the candidate profile (any industry / domain)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.llm_client import chat_json, llm_configured
from app.services.resume_experience_years import experience_search_phrase, infer_total_experience_years

log = logging.getLogger(__name__)


def _clean_title(t: str) -> str:
    s = (t or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s[:160] if s else ""


def _merge_competencies(sk: dict[str, Any] | Any) -> list[str]:
    if not isinstance(sk, dict):
        return []
    parts: list[str] = []
    for key in ("technical", "tools", "soft", "certifications"):
        for x in sk.get(key) or []:
            if isinstance(x, str) and x.strip():
                parts.append(x.strip())
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        low = p.lower()
        if low not in seen:
            seen.add(low)
            out.append(p)
    return out[:50]


def _resume_brief(resume_json: dict[str, Any]) -> dict[str, Any]:
    contact = resume_json.get("contact") or {}
    exp = resume_json.get("experience") or []
    sk = resume_json.get("skills") or {}
    if not isinstance(sk, dict):
        sk = {}
    roles = []
    for e in exp[:8]:
        if isinstance(e, dict):
            t = (e.get("title") or "").strip()
            c = (e.get("company") or "").strip()
            sd = str(e.get("start_date") or "").strip()
            ed = str(e.get("end_date") or "").strip()
            if t or c:
                roles.append({"title": t, "company": c, "start_date": sd, "end_date": ed})
    years = infer_total_experience_years(resume_json or {})
    exp_hint = experience_search_phrase(years)
    competencies = _merge_competencies(sk)
    langs = [str(x).strip() for x in (resume_json.get("languages") or []) if str(x).strip()][:12]
    return {
        "name": (contact.get("name") or "").strip(),
        "phone_country_hint": (contact.get("phone") or "").strip()[:8],
        "headline_summary": (resume_json.get("summary") or "")[:2000],
        "roles": roles,
        "technical_skills": (sk.get("technical") or [])[:40],
        "tools": (sk.get("tools") or [])[:30],
        "soft_skills": (sk.get("soft") or [])[:30],
        "certifications_list": (sk.get("certifications") or [])[:25],
        "all_competencies": competencies,
        "languages": langs,
        "estimated_years_experience": years,
        "experience_query_hint": exp_hint,
    }


def _heuristic_titles_from_resume(brief: dict[str, Any]) -> list[str]:
    """
    Derive search titles only from resume content (no domain presets).
    Prefer past job titles; otherwise the first substantive line of the summary.
    """
    seen: set[str] = set()
    out: list[str] = []

    for r in brief.get("roles") or []:
        if not isinstance(r, dict):
            continue
        t = _clean_title(str(r.get("title") or ""))
        if len(t) < 2:
            continue
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(t)
        if len(out) >= 8:
            break

    summary = (brief.get("headline_summary") or "").strip()
    if len(out) < 4 and summary:
        first_line = re.split(r"[\n.]", summary, maxsplit=1)[0].strip()
        if 20 <= len(first_line) <= 140:
            low = first_line.lower()
            if low not in seen:
                seen.add(low)
                out.append(first_line)

    if not out and summary:
        snippet = re.sub(r"\s+", " ", summary)[:100].strip()
        if len(snippet) > 12:
            out.append(snippet)

    if not out:
        out = ["Professional roles"]

    return out[:8]


def _append_experience_to_queries(queries: list[str], exp_hint: str) -> list[str]:
    if not exp_hint.strip():
        return queries
    out: list[str] = []
    low_hint = exp_hint.lower()
    for q in queries:
        s = (q or "").strip()
        if not s:
            continue
        if low_hint not in s.lower():
            s = f"{s} {exp_hint}".strip()
        out.append(s)
    return out


def _heuristic_role_queries(brief: dict[str, Any]) -> dict[str, Any]:
    """No LLM key: build queries only from titles + competencies on the resume."""
    role_templates = _heuristic_titles_from_resume(brief)
    comps = [str(x) for x in (brief.get("all_competencies") or [])][:6]
    tech_chunk = " ".join(comps).strip()
    queries: list[str] = []
    seen: set[str] = set()
    for title in role_templates[:6]:
        base = f"{title} {tech_chunk}".strip() + " jobs"
        base = re.sub(r"\s+", " ", base).strip()
        low = base.lower()
        if low not in seen:
            seen.add(low)
            queries.append(base)
    exp_hint = str(brief.get("experience_query_hint") or "").strip()
    queries = _append_experience_to_queries(queries, exp_hint)
    role_labels = role_templates[:8]
    phone = str(brief.get("phone_country_hint") or "")
    if phone.startswith("+91"):
        country = "in"
    elif phone.startswith("+44"):
        country = "gb"
    elif phone.startswith("+61"):
        country = "au"
    else:
        country = "us"
    return {
        "queries": queries,
        "country": country,
        "location_phrase": "",
        "role_titles": role_labels,
        "query_plan_source": "heuristic",
    }


_SYSTEM_PROMPT = """You output ONLY valid JSON for a job-search assistant. The candidate may work in ANY field: technology, healthcare, education, finance, legal, trades, retail, government, nonprofit, creative arts, operations, hospitality, agriculture, etc.

Keys:
- role_titles: array of 5 to 6 DISTINCT, realistic JOB TITLES the candidate would plausibly search for next (standard titles for their field, not company names). Infer these ONLY from the provided resume_json: past job titles, summary, skills (technical, tools, soft), certifications, and languages. Do not use education. If the resume is sparse, infer a small set of adjacent roles that match the same career level and domain.
- queries: array of the SAME length as role_titles. Each string must be one role_title plus 2 to 6 relevant skills, tools, certifications, or domain keywords taken from the resume, plus the word "jobs" — suitable for Indeed/Google-style job search. Use non-English role names only if the resume is clearly in that language.
- country: ISO 3166-1 alpha-2 best guess from the phone country code (default "us" if unknown).
- location_phrase: always an empty string. Do not extract or infer a location from the resume.

Rules:
- Do NOT assume software engineering or data science unless the resume supports it.
- Do NOT invent employers or job descriptions; use resume facts only.
- Align seniority with estimated_years_experience (entry vs mid vs senior).
- The resume_json includes experience_query_hint: when it is non-empty, append that EXACT substring to EVERY query string (if not already present)."""


async def suggest_jsearch_queries(resume_json: dict[str, Any]) -> dict[str, Any]:
    """
    Build board-search query strings from resume only (any domain).
    Returns keys: queries, country, location_phrase, role_titles.
    """
    brief = _resume_brief(resume_json or {})

    if not llm_configured():
        return _heuristic_role_queries(brief)

    user_payload = json.dumps({"resume_json": brief}, ensure_ascii=False)
    try:
        data = await chat_json(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.35,
            max_tokens=1100,
        )
        queries = data.get("queries") or []
        if not isinstance(queries, list):
            queries = []
        queries = [str(q).strip() for q in queries if str(q).strip()][:8]
        role_titles = data.get("role_titles") or []
        if not isinstance(role_titles, list):
            role_titles = []
        role_titles = [str(t).strip() for t in role_titles if str(t).strip()][:8]
        country = str(data.get("country") or "us").strip().lower()[:2] or "us"
        # Location is a separate instant UI filter, never inferred from resume content.
        loc = ""
        if not queries:
            out = _heuristic_role_queries(brief)
            out["query_plan_source"] = "heuristic_empty_llm_queries"
            return out
        exp_hint = str(brief.get("experience_query_hint") or "").strip()
        queries = _append_experience_to_queries(queries, exp_hint)
        if not role_titles:
            role_titles = _heuristic_titles_from_resume(brief)[:8]
        if len(queries) < len(role_titles):
            for idx in range(len(queries), min(len(role_titles), 8)):
                t = role_titles[idx]
                extra = f"{t} jobs".strip()
                if exp_hint and exp_hint.lower() not in extra.lower():
                    extra = f"{extra} {exp_hint}".strip()
                queries.append(extra)
        queries = queries[:8]
        return {
            "queries": queries,
            "country": country,
            "location_phrase": loc,
            "role_titles": role_titles,
            "query_plan_source": "openai",
        }
    except Exception as e:
        log.warning("suggest_jsearch_queries LLM failed: %s", e)
        out = _heuristic_role_queries(brief)
        out["query_plan_source"] = "heuristic_llm_error"
        return out
