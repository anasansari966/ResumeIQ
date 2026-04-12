"""Normalize parsed resume JSON: fix placeholders, ensure schema shape, optional LLM repair."""
import json
import logging
import re
from typing import Any

from app.config import settings
from app.schemas import ContactBlock, EducationItem, ExperienceItem, ProjectItem, ResumeSchema, SkillsBlock
from app.services.entity_normalize import normalize_resume_entities
from app.services.resume_parser import (
    _strip_contact_noise_from_summary,
    contact_location_fallback,
    fill_education_gpa_from_text,
    set_summary_origin_from_text,
)
from app.services.resume_salvage import comprehensive_salvage

log = logging.getLogger(__name__)

_SUMMARY_MIN_LEN = 35

_PLACEHOLDER_COMPANY = frozenset(
    {
        "(see full resume)",
        "see full resume",
        "see resume",
        "see full cv",
        "—",
        "-",
        "n/a",
        "na",
        "full resume",
    }
)


def _bad_title(t: str) -> bool:
    low = (t or "").strip().lower()
    return low in ("professional experience", "work experience", "experience", "employment") and len(low) < 40


def rule_normalize_resume(parsed: dict[str, Any], cleaned_text: str) -> dict[str, Any]:
    """Deterministic cleanup and shape guarantees."""
    meta_keys = {k: v for k, v in parsed.items() if str(k).startswith("_resumeiq")}
    contact = ContactBlock.model_validate(parsed.get("contact") or {})
    summary = _strip_contact_noise_from_summary(str(parsed.get("summary") or ""), contact)

    exp_out: list[dict[str, Any]] = []
    for e in parsed.get("experience") or []:
        if not isinstance(e, dict):
            continue
        company = (e.get("company") or "").strip()
        title = (e.get("title") or "").strip()
        low = company.lower()
        if not company or low in _PLACEHOLDER_COMPANY or "see full" in low:
            company = ""
        if _bad_title(title) and not company:
            title = ""
        bullets = [str(b).strip() for b in (e.get("bullets") or []) if str(b).strip()]
        desc = [str(d).strip() for d in (e.get("description") or []) if str(d).strip()]
        if not company and not title and bullets:
            title = "Key contributions"
            company = "—"
        if not company and title and bullets:
            company = "—"
        exp_out.append(
            {
                "company": company or "—",
                "title": title or "",
                "start_date": str(e.get("start_date") or ""),
                "end_date": str(e.get("end_date") or ""),
                "description": desc,
                "bullets": bullets or ["Add role details from your resume."],
            }
        )
    if not exp_out:
        exp_out.append(
            {
                "company": "—",
                "title": "",
                "start_date": "",
                "end_date": "",
                "description": [],
                "bullets": ["Experience could not be segmented — edit in Tailor step or re-upload."],
            }
        )

    edu_out: list[dict[str, Any]] = []
    for ed in parsed.get("education") or []:
        if not isinstance(ed, dict):
            continue
        edu_out.append(
            {
                "institution": str(ed.get("institution") or "").strip() or "—",
                "degree": str(ed.get("degree") or "").strip(),
                "field": str(ed.get("field") or "").strip(),
                "year": str(ed.get("year") or "").strip(),
                "gpa": ed.get("gpa"),
            }
        )

    proj_out: list[dict[str, Any]] = []
    for p in parsed.get("projects") or []:
        if not isinstance(p, dict):
            continue
        ts = p.get("tech_stack") or []
        if isinstance(ts, str):
            ts = [x.strip() for x in re.split(r"[,;]", ts) if x.strip()]
        proj_out.append(
            {
                "name": str(p.get("name") or "").strip() or "Project",
                "description": str(p.get("description") or "").strip(),
                "tech_stack": list(ts) if isinstance(ts, list) else [],
                "link": p.get("link"),
            }
        )

    if not proj_out and cleaned_text:
        proj_out = _extract_projects_heuristic(cleaned_text)

    sk = parsed.get("skills") or {}
    if not isinstance(sk, dict):
        sk = {}
    skills = SkillsBlock(
        technical=[str(x).strip() for x in (sk.get("technical") or []) if str(x).strip()],
        soft=[str(x).strip() for x in (sk.get("soft") or []) if str(x).strip()],
        tools=[str(x).strip() for x in (sk.get("tools") or []) if str(x).strip()],
        certifications=[str(x).strip() for x in (sk.get("certifications") or []) if str(x).strip()],
    )

    so = parsed.get("summary_origin")
    if so not in ("document", "model"):
        so = "model"
    resume = ResumeSchema(
        contact=contact,
        summary=summary,
        summary_origin=so,
        experience=[ExperienceItem.model_validate(x) for x in exp_out],
        education=[EducationItem.model_validate(x) for x in edu_out],
        skills=skills,
        projects=[ProjectItem.model_validate(x) for x in proj_out],
        languages=[str(x) for x in (parsed.get("languages") or []) if str(x).strip()],
        publications=[str(x) for x in (parsed.get("publications") or []) if str(x).strip()],
        awards=[str(x) for x in (parsed.get("awards") or []) if str(x).strip()],
        leadership=[str(x) for x in (parsed.get("leadership") or []) if str(x).strip()],
        extracurricular=[str(x) for x in (parsed.get("extracurricular") or []) if str(x).strip()],
        ats_score_baseline=parsed.get("ats_score_baseline"),
    )
    out = resume.model_dump()
    out.update(meta_keys)
    return out


def _extract_projects_heuristic(text: str) -> list[dict[str, Any]]:
    """Light extraction if a Projects section exists in plain text."""
    projects: list[dict[str, Any]] = []
    m = re.search(
        r"\bprojects?\b\s*[:\n]+(.*?)(?=\b(education|skills|experience|certifications)\b|$)",
        text,
        flags=re.I | re.S,
    )
    if not m:
        return []
    block = m.group(1).strip()
    for line in block.splitlines():
        t = line.strip()
        if not t or len(t) < 4:
            continue
        if t[:1] in "•-*–" or re.match(r"^\d+\.", t):
            name = t.lstrip("•-*–0123456789.) ").strip()[:120]
            if name:
                projects.append({"name": name, "description": "", "tech_stack": [], "link": None})
        elif ":" in t and len(t) < 200:
            name, rest = t.split(":", 1)
            projects.append({"name": name.strip()[:120], "description": rest.strip()[:500], "tech_stack": [], "link": None})
    return projects[:12]


async def llm_repair_resume_json(parsed: dict[str, Any], cleaned_text: str) -> dict[str, Any]:
    """Second pass: align JSON with full text (education, projects, employers)."""
    from openai import AsyncOpenAI

    from app.services.resume_salvage import strip_resume_internal_keys

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    schema_keys = list(ResumeSchema.model_json_schema().get("properties", {}).keys())
    system = (
        "You output ONLY valid JSON for ResumeSchema. "
        "Input includes draft_resume_json (may have wrong placeholders) and resume_text. "
        "Fix: (1) summary = 2–5 sentences professional focus ONLY — zero contact info or symbols. "
        "(2) experience: real employer names and titles from text; never use '(see full resume)' as company; "
        "group bullets under the correct employer. If employers not explicit, ONE block with company '—' and accurate bullets. "
        "(3) education: every school/degree/year from text. "
        "(4) projects: named projects with description/tech if present. "
        "(5) skills.technical flat list, no broken tokens. "
        "Facts only from resume_text — do not invent employers or degrees."
    )
    payload = json.dumps(
        {
            "draft_resume_json": strip_resume_internal_keys(parsed),
            "resume_text": cleaned_text[:14_000],
        },
        ensure_ascii=False,
    )
    resp = await client.chat.completions.create(
        model=settings.openai_parse_model,
        messages=[
            {"role": "system", "content": system + f"\nKeys: {schema_keys}"},
            {"role": "user", "content": payload},
        ],
        response_format={"type": "json_object"},
        temperature=0.05,
    )
    text = resp.choices[0].message.content or "{}"
    data = json.loads(text)
    resume = ResumeSchema.model_validate(data)
    dumped = resume.model_dump()
    contact = ContactBlock.model_validate(dumped.get("contact") or {})
    dumped["summary"] = _strip_contact_noise_from_summary(dumped.get("summary") or "", contact)
    meta_keys = {k: v for k, v in parsed.items() if str(k).startswith("_resumeiq")}
    dumped.update(meta_keys)
    return dumped


async def ensure_summary_if_missing(parsed: dict[str, Any], cleaned_text: str) -> dict[str, Any]:
    """Use OpenAI when summary is missing or too short after deterministic passes."""
    s = str(parsed.get("summary") or "").strip()
    if s and len(s) >= _SUMMARY_MIN_LEN:
        return parsed
    if not settings.openai_api_key:
        return parsed
    from openai import AsyncOpenAI

    from app.services.resume_salvage import strip_resume_internal_keys

    contact = ContactBlock.model_validate(parsed.get("contact") or {})
    brief = strip_resume_internal_keys(parsed)
    excerpt = (cleaned_text or "")[:10_000]
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    sys = (
        "Write a professional resume summary: exactly 2–4 sentences. "
        "Focus on role, years/domain, and top strengths inferred ONLY from the provided facts. "
        "No contact details, phone, email, URLs, city-only lines, or section headings."
    )
    payload = json.dumps({"resume_json": brief, "resume_text_excerpt": excerpt}, ensure_ascii=False)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_parse_model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": payload}],
            temperature=0.25,
            max_tokens=280,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return parsed
        parsed = dict(parsed)
        parsed["summary"] = _strip_contact_noise_from_summary(text, contact)
        return parsed
    except Exception as e:
        log.warning("ensure_summary_if_missing failed: %s", e)
        return parsed


async def finalize_resume(parsed: dict[str, Any], cleaned_text: str) -> dict[str, Any]:
    meta = parsed.get("_resumeiq_cleaned")
    base = {k: v for k, v in parsed.items() if not str(k).startswith("_resumeiq")}
    if meta:
        base["_resumeiq_cleaned"] = meta
    normalized = rule_normalize_resume(base, cleaned_text)
    if settings.openai_api_key:
        try:
            normalized = await llm_repair_resume_json(normalized, cleaned_text)
            normalized = rule_normalize_resume(normalized, cleaned_text)
        except Exception as e:
            log.warning("llm_repair_resume_json failed: %s", e)
    normalized = comprehensive_salvage(normalized, cleaned_text)
    normalized = rule_normalize_resume(normalized, cleaned_text)
    if settings.openai_api_key:
        normalized = await ensure_summary_if_missing(normalized, cleaned_text)
        normalized = rule_normalize_resume(normalized, cleaned_text)
    normalized = normalize_resume_entities(normalized)
    fill_education_gpa_from_text(normalized, cleaned_text)
    contact_location_fallback(normalized, cleaned_text)
    set_summary_origin_from_text(normalized, cleaned_text)
    normalized = rule_normalize_resume(normalized, cleaned_text)
    return normalized
