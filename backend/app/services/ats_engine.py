import re
from typing import Any

from app.services.jd_analysis import extract_keywords_jd


def _flatten_resume_text(resume_json: dict[str, Any]) -> str:
    """Lowercased bag-of-text for JD keyword matching — include all major sections."""
    parts: list[str] = []
    c = resume_json.get("contact") or {}
    for k in ("name", "email", "phone", "location", "linkedin", "github"):
        parts.append(str(c.get(k, "")))
    parts.append(str(resume_json.get("summary", "")))
    for exp in resume_json.get("experience") or []:
        parts.append(" ".join([str(exp.get("title", "")), str(exp.get("company", ""))]))
        for b in exp.get("bullets") or []:
            parts.append(str(b))
        for b in exp.get("description") or []:
            parts.append(str(b))
    for edu in resume_json.get("education") or []:
        parts.append(" ".join([str(edu.get("degree", "")), str(edu.get("field", "")), str(edu.get("institution", ""))]))
    for pr in resume_json.get("projects") or []:
        parts.append(str(pr.get("name", "")))
        parts.append(str(pr.get("description", "")))
        for t in pr.get("tech_stack") or []:
            parts.append(str(t))
    for pub in resume_json.get("publications") or []:
        parts.append(str(pub))
    for lang in resume_json.get("languages") or []:
        parts.append(str(lang))
    sk = resume_json.get("skills") or {}
    for key in ("technical", "soft", "tools", "certifications"):
        for s in sk.get(key) or []:
            parts.append(str(s))
    return " ".join(parts).lower()


def _format_sections_score(resume_json: dict[str, Any]) -> float:
    """Reward clear resume structure (not random words like 'experience' in bullets)."""
    has_exp = bool(resume_json.get("experience"))
    has_edu = bool(resume_json.get("education"))
    sk = resume_json.get("skills") or {}
    has_skills = bool(sk.get("technical") or sk.get("tools") or sk.get("soft"))
    hits = sum([has_exp, has_edu, has_skills])
    return min(1.0, hits / 3)


def _quantification_ratio(resume_json: dict[str, Any]) -> float:
    bullets: list[str] = []
    for exp in resume_json.get("experience") or []:
        bullets.extend(exp.get("bullets") or [])
    if not bullets:
        return 0.3
    with_num = sum(1 for b in bullets if re.search(r"\d", b))
    return with_num / max(1, len(bullets))


def _completeness(resume_json: dict[str, Any]) -> float:
    score = 0.0
    if (resume_json.get("summary") or "").strip():
        score += 0.25
    if resume_json.get("experience"):
        score += 0.35
    if resume_json.get("education"):
        score += 0.2
    sk = resume_json.get("skills") or {}
    if any(sk.get(k) for k in ("technical", "tools")):
        score += 0.2
    return min(1.0, score)


def _length_score(resume_json: dict[str, Any]) -> float:
    n_exp = len(resume_json.get("experience") or [])
    n_bul = sum(len(e.get("bullets") or []) for e in resume_json.get("experience") or [])
    if n_bul <= 14:
        return 1.0
    if n_bul <= 22:
        return 0.85
    return 0.7


def score_resume_jd(resume_json: dict[str, Any], jd_text: str = "", jd_keywords: list[str] | None = None) -> tuple[float, dict[str, float], list[str]]:
    flat = _flatten_resume_text(resume_json)
    if jd_keywords is None and jd_text:
        jd_keywords = extract_keywords_jd(jd_text, top_n=35)
    elif jd_keywords is None:
        jd_keywords = []
    if not jd_keywords and jd_text:
        jd_keywords = extract_keywords_jd(jd_text)

    matched = 0
    kw_slice = [str(k).strip() for k in (jd_keywords or [])[:35] if str(k).strip()]
    for kw in kw_slice:
        if kw.lower() in flat:
            matched += 1
    n_kw = len(kw_slice)
    if n_kw == 0:
        keyword_match = 0.58
    else:
        keyword_match = min(1.0, matched / max(n_kw, 1))

    fmt = _format_sections_score(resume_json)
    format_ok = 0.88 if fmt >= 0.66 else 0.62 if fmt >= 0.33 else 0.48
    content_ok = _completeness(resume_json)
    quant = _quantification_ratio(resume_json)
    length_ok = _length_score(resume_json)

    sk = resume_json.get("skills") or {}
    tech = [t.lower() for t in (sk.get("technical") or []) + (sk.get("tools") or [])]
    skill_align = 0.55
    if kw_slice:
        uniq = list(dict.fromkeys(k.lower() for k in kw_slice[:24]))
        overlap = sum(1 for k in uniq if k in tech or k in flat)
        skill_align = min(1.0, overlap / max(len(uniq), 1))

    weights = {
        "keyword_match": 0.35,
        "format_compliance": 0.20,
        "content_completeness": 0.20,
        "quantification": 0.10,
        "length": 0.08,
        "skills_alignment": 0.07,
    }
    dims = {
        "keyword_match": round(100 * keyword_match, 1),
        "format_compliance": round(100 * format_ok, 1),
        "content_completeness": round(100 * content_ok, 1),
        "quantification": round(100 * quant, 1),
        "length_optimization": round(100 * length_ok, 1),
        "skills_alignment": round(100 * skill_align, 1),
    }
    overall = (
        weights["keyword_match"] * dims["keyword_match"]
        + weights["format_compliance"] * dims["format_compliance"]
        + weights["content_completeness"] * dims["content_completeness"]
        + weights["quantification"] * dims["quantification"]
        + weights["length"] * dims["length_optimization"]
        + weights["skills_alignment"] * dims["skills_alignment"]
    )
    overall = round(min(100, max(0, overall)), 1)

    suggestions: list[str] = []
    if dims["keyword_match"] < 70:
        missing = [k for k in jd_keywords[:12] if k.lower() not in flat][:5]
        if missing:
            suggestions.append(f"Weave these JD terms naturally into bullets: {', '.join(missing)}.")
    if dims["quantification"] < 55:
        suggestions.append("Add metrics to bullets (%, revenue, latency, team size, scale).")
    if dims["content_completeness"] < 70:
        suggestions.append("Fill Summary, Experience, Education, and a focused Skills section.")
    if dims["skills_alignment"] < 60:
        suggestions.append("Reorder skills so the most JD-relevant tools appear first.")
    if not suggestions:
        suggestions.append("Strong alignment — tweak summary tone to mirror the JD voice.")

    return overall, dims, suggestions
