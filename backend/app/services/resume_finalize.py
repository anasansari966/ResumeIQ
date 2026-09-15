"""Normalize parsed resume JSON: fix placeholders, ensure schema shape, optional LLM repair."""
import json
import logging
import re
from typing import Any

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
    from app.services.llm_client import chat_json
    from app.services.resume_salvage import strip_resume_internal_keys

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
    data = await chat_json(
        [
            {"role": "system", "content": system + f"\nKeys: {schema_keys}"},
            {"role": "user", "content": payload},
        ],
        temperature=0.05,
        max_tokens=8192,
    )
    resume = ResumeSchema.model_validate(data)
    dumped = resume.model_dump()
    contact = ContactBlock.model_validate(dumped.get("contact") or {})
    dumped["summary"] = _strip_contact_noise_from_summary(dumped.get("summary") or "", contact)
    meta_keys = {k: v for k, v in parsed.items() if str(k).startswith("_resumeiq")}
    dumped.update(meta_keys)
    return dumped


async def structure_resume_for_ats_template(
    parsed: dict[str, Any],
    cleaned_text: str,
    *,
    template_name: str = "",
    template_style: str = "",
) -> dict[str, Any]:
    """
    Use OpenAI to reorganize extracted resume facts into a clean ATS-ready schema
    covering every section mentioned in the source (contact, summary, experience,
    education, skills, projects, certifications, languages, awards, etc.).
    """
    from app.services.llm_client import chat_json, llm_configured
    from app.services.resume_salvage import strip_resume_internal_keys

    if not llm_configured():
        return rule_normalize_resume(parsed, cleaned_text)

    draft = strip_resume_internal_keys(parsed)
    source_text = (cleaned_text or "").strip() or str(parsed.get("_resumeiq_cleaned") or "").strip()
    if len(source_text) < 80:
        # Fall back to any raw text fields that may still be on the draft.
        for key in ("raw_text", "full_text", "text"):
            extra = str(parsed.get(key) or "").strip()
            if len(extra) > len(source_text):
                source_text = extra

    schema_example = {
        "contact": {
            "name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
        },
        "summary": "",
        "summary_origin": "document",
        "experience": [
            {
                "company": "",
                "title": "",
                "start_date": "",
                "end_date": "",
                "bullets": ["achievement"],
                "description": [],
            }
        ],
        "education": [
            {
                "institution": "",
                "degree": "",
                "field": "",
                "year": "",
                "gpa": None,
            }
        ],
        "skills": {
            "technical": ["skill"],
            "soft": [],
            "tools": [],
            "certifications": [],
        },
        "projects": [
            {
                "name": "",
                "description": "",
                "tech_stack": [],
                "link": None,
            }
        ],
        "languages": [],
        "publications": [],
        "awards": [],
        "leadership": [],
        "extracurricular": [],
    }

    system = (
        "You are an ATS resume structuring engine. Output ONLY valid JSON matching ResumeSchema.\n"
        f"Target template: {template_name or 'ATS resume'} ({template_style or 'ATS'}).\n\n"
        "GOAL: Capture EVERY section and fact mentioned in the resume text and draft JSON. "
        "Do not drop content. Reorganize and clean wording, but keep coverage complete.\n\n"
        "REQUIRED SECTIONS (fill from source when present; use [] / \"\" when truly absent):\n"
        "1) contact — name, email, phone, location, linkedin, github\n"
        "2) summary — 2–4 ATS sentences (role, domain, impact). No contact info. "
        "If a Summary/Objective/Profile exists in the resume, rewrite from that; else synthesize from experience.\n"
        "3) experience — ALL jobs/internships reverse-chronological. Real company + title + dates when known. "
        "3–8 concise achievement bullets each (action + result). Never invent employers.\n"
        "4) education — ALL schools/degrees/fields/years/GPA mentioned.\n"
        "5) skills — technical, tools, soft, and certifications as separate lists (deduped ATS keywords).\n"
        "6) projects — ALL named projects with description + tech_stack when present.\n"
        "7) languages, publications, awards, leadership, extracurricular — include every item found.\n\n"
        "RULES:\n"
        "- Prefer resume_text as ground truth; use draft_resume_json to recover structure already extracted.\n"
        "- If draft has a section the text also supports, keep/improve it — do not empty it.\n"
        "- Never fabricate employers, degrees, projects, or certifications.\n"
        "- summary_origin = \"document\" if a summary exists in the source, else \"model\".\n"
        f"- Shape example (types only): {json.dumps(schema_example, ensure_ascii=False)}"
    )
    payload = json.dumps(
        {
            "draft_resume_json": draft,
            "resume_text": source_text[:16_000],
            "template_name": template_name,
            "template_style": template_style,
            "must_include_if_present": [
                "experience",
                "education",
                "skills",
                "projects",
                "certifications",
                "languages",
                "awards",
                "leadership",
                "extracurricular",
                "publications",
            ],
        },
        ensure_ascii=False,
    )
    try:
        data = await chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": payload},
            ],
            temperature=0.1,
            max_tokens=8192,
        )
        resume = ResumeSchema.model_validate(data)
        dumped = resume.model_dump()
        contact = ContactBlock.model_validate(dumped.get("contact") or {})
        dumped["summary"] = _strip_contact_noise_from_summary(dumped.get("summary") or "", contact)
        dumped = _backfill_empty_sections(dumped, draft)
        meta_keys = {k: v for k, v in parsed.items() if str(k).startswith("_resumeiq")}
        dumped.update(meta_keys)
        return rule_normalize_resume(dumped, source_text)
    except Exception as exc:  # noqa: BLE001
        log.warning("structure_resume_for_ats_template failed: %s", exc)
        # Fall back to full finalize with LLM repair when possible.
        try:
            return await finalize_resume(parsed, source_text or cleaned_text, use_llm=True)
        except Exception as inner:  # noqa: BLE001
            log.warning("finalize fallback failed: %s", inner)
            return rule_normalize_resume(parsed, source_text or cleaned_text)


def _section_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_section_nonempty(x) for x in value)
    if isinstance(value, dict):
        return any(_section_nonempty(v) for v in value.values())
    return True


def _backfill_empty_sections(structured: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    """If the LLM omitted a section that the draft already had, keep the draft content."""
    out = dict(structured or {})
    src = draft or {}

    for key in (
        "experience",
        "education",
        "projects",
        "languages",
        "publications",
        "awards",
        "leadership",
        "extracurricular",
    ):
        if not _section_nonempty(out.get(key)) and _section_nonempty(src.get(key)):
            out[key] = src.get(key)

    out_skills = out.get("skills") if isinstance(out.get("skills"), dict) else {}
    src_skills = src.get("skills") if isinstance(src.get("skills"), dict) else {}
    merged_skills = dict(out_skills)
    for sk in ("technical", "soft", "tools", "certifications"):
        if not _section_nonempty(merged_skills.get(sk)) and _section_nonempty(src_skills.get(sk)):
            merged_skills[sk] = src_skills.get(sk)
        elif _section_nonempty(merged_skills.get(sk)) and _section_nonempty(src_skills.get(sk)):
            # Union while preserving LLM order first.
            seen: set[str] = set()
            combined: list[str] = []
            for item in list(merged_skills.get(sk) or []) + list(src_skills.get(sk) or []):
                s = str(item).strip()
                low = s.lower()
                if not s or low in seen:
                    continue
                seen.add(low)
                combined.append(s)
            merged_skills[sk] = combined
    out["skills"] = merged_skills

    if not _section_nonempty(out.get("summary")) and _section_nonempty(src.get("summary")):
        out["summary"] = src.get("summary")

    contact = out.get("contact") if isinstance(out.get("contact"), dict) else {}
    src_contact = src.get("contact") if isinstance(src.get("contact"), dict) else {}
    merged_contact = dict(contact)
    for field in ("name", "email", "phone", "location", "linkedin", "github"):
        if not str(merged_contact.get(field) or "").strip() and str(src_contact.get(field) or "").strip():
            merged_contact[field] = src_contact.get(field)
    out["contact"] = merged_contact
    return out


async def ensure_summary_if_missing(parsed: dict[str, Any], cleaned_text: str) -> dict[str, Any]:
    """Use OpenAI when summary is missing or too short after deterministic passes."""
    from app.services.llm_client import chat_complete, llm_configured

    s = str(parsed.get("summary") or "").strip()
    if s and len(s) >= _SUMMARY_MIN_LEN:
        return parsed
    if not llm_configured():
        return parsed

    from app.services.resume_salvage import strip_resume_internal_keys

    contact = ContactBlock.model_validate(parsed.get("contact") or {})
    brief = strip_resume_internal_keys(parsed)
    excerpt = (cleaned_text or "")[:10_000]
    sys = (
        "Write a professional resume summary: exactly 2–4 sentences. "
        "Focus on role, years/domain, and top strengths inferred ONLY from the provided facts. "
        "No contact details, phone, email, URLs, city-only lines, or section headings."
    )
    payload = json.dumps({"resume_json": brief, "resume_text_excerpt": excerpt}, ensure_ascii=False)
    try:
        text = await chat_complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": payload}],
            temperature=0.25,
            max_tokens=280,
        )
        text = (text or "").strip()
        if not text:
            return parsed
        parsed = dict(parsed)
        parsed["summary"] = _strip_contact_noise_from_summary(text, contact)
        return parsed
    except Exception as e:
        log.warning("ensure_summary_if_missing failed: %s", e)
        return parsed


async def finalize_resume(parsed: dict[str, Any], cleaned_text: str, *, use_llm: bool = True) -> dict[str, Any]:
    from app.services.llm_client import llm_configured

    meta = parsed.get("_resumeiq_cleaned")
    base = {k: v for k, v in parsed.items() if not str(k).startswith("_resumeiq")}
    if meta:
        base["_resumeiq_cleaned"] = meta
    normalized = rule_normalize_resume(base, cleaned_text)
    if use_llm and llm_configured():
        try:
            normalized = await llm_repair_resume_json(normalized, cleaned_text)
            normalized = rule_normalize_resume(normalized, cleaned_text)
        except Exception as e:
            log.warning("llm_repair_resume_json failed: %s", e)
    normalized = comprehensive_salvage(normalized, cleaned_text)
    normalized = rule_normalize_resume(normalized, cleaned_text)
    if use_llm and llm_configured():
        normalized = await ensure_summary_if_missing(normalized, cleaned_text)
        normalized = rule_normalize_resume(normalized, cleaned_text)
    normalized = normalize_resume_entities(normalized)
    fill_education_gpa_from_text(normalized, cleaned_text)
    contact_location_fallback(normalized, cleaned_text)
    set_summary_origin_from_text(normalized, cleaned_text)
    normalized = rule_normalize_resume(normalized, cleaned_text)
    return normalized
