import json
import re
from typing import Any, AsyncIterator

from app.schemas import ResumeSchema
from app.services.resume_salvage import strip_resume_internal_keys


def _norm_bullet(s: str) -> str:
    t = (s or "").replace("\u200b", "")
    t = re.sub(r"[\r\n]+", " ", t)
    t = re.sub(r" +", " ", t).strip()
    return t


def _mock_tailor(parsed_resume: dict[str, Any], jd_analysis: dict[str, Any]) -> dict[str, Any]:
    base = ResumeSchema.model_validate(strip_resume_internal_keys(parsed_resume)).model_dump()
    keywords = jd_analysis.get("must_have_keywords") or jd_analysis.get("keywords") or []
    keywords = [str(k).strip() for k in keywords if str(k).strip()]
    tech_in = (base.get("skills") or {}).get("technical") or []
    skills = list(dict.fromkeys(tech_in + keywords[:12]))[:24]

    summary = (base.get("summary") or "").strip()
    if keywords and summary:
        tail = ", ".join(keywords[:6])
        add = f" Emphasis for this role: {tail}." if tail else ""
        base["summary"] = (summary + add).strip()[:1200]
    elif keywords:
        base["summary"] = (
            "Professional summary: highlight impact and tools below; role themes include " + ", ".join(keywords[:10]) + "."
        )[:1200]
    else:
        base["summary"] = summary[:1200]

    if base.get("experience"):
        kw_tail = ", ".join(keywords[:4]) if keywords else ""
        for i, exp in enumerate(base["experience"]):
            bullets = [_norm_bullet(b) for b in (exp.get("bullets") or []) if _norm_bullet(b)]
            if not bullets and (exp.get("description") or []):
                bullets = [_norm_bullet(d) for d in exp.get("description") or [] if _norm_bullet(d)]
            if kw_tail and bullets and not any(
                str(k).lower() in bullets[0].lower() for k in keywords[:6] if str(k).strip()
            ):
                bullets[0] = (bullets[0].rstrip(".") + f" ({kw_tail}).")[:500]
            exp["bullets"] = bullets[:14]
            base["experience"][i] = exp

    base["skills"] = base.get("skills") or {}
    base["skills"]["technical"] = skills
    return base


async def generate_tailored_resume(
    parsed_resume: dict[str, Any], jd_analysis: dict[str, Any], raw_jd: str
) -> dict[str, Any]:
    from app.services.llm_client import chat_json, llm_configured

    parsed_resume = strip_resume_internal_keys(parsed_resume)
    if not llm_configured():
        return _mock_tailor(parsed_resume, jd_analysis)
    try:
        schema_hint = ResumeSchema.model_json_schema()
        kws = jd_analysis.get("must_have_keywords") or jd_analysis.get("keywords") or []
        kw_preview = ", ".join(str(x).strip() for x in kws[:18] if str(x).strip())
        system = (
            "You are an expert resume writer. Return ONLY valid JSON matching ResumeSchema. "
            "Never fabricate employers, degrees, or dates. Use only facts from the candidate JSON. "
            "Rewrite bullets with strong verbs and quantified impact (%, counts, scale, latency, accuracy) wherever the source allows inference. "
            "Naturally weave JD must-have terms into summary, skills.technical (most relevant first), and experience bullets — do not keyword-stuff. "
            f"JD terms to reflect when truthful: {kw_preview or '(see jd_analysis)'}. "
            "summary must be 2–4 professional sentences only: no email, phone, URLs, icons, or contact lines. "
            "Never add generic filler bullets; every bullet must reflect real content. "
            "Keep education and projects when present; enrich project descriptions with role-relevant phrasing only if grounded in the original."
        )
        user_payload = {
            "candidate_resume": parsed_resume,
            "jd_analysis": jd_analysis,
            "job_description_excerpt": raw_jd[:6000],
        }
        data = await chat_json(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(user_payload)
                    + f"\n\nSchema keys: {list(schema_hint.get('properties', {}).keys())}",
                },
            ],
            temperature=0.4,
            max_tokens=8192,
        )
        validated = ResumeSchema.model_validate(data)
        return validated.model_dump()
    except Exception:
        return _mock_tailor(parsed_resume, jd_analysis)


async def stream_tailored_resume_tokens(
    parsed_resume: dict[str, Any], jd_analysis: dict[str, Any], raw_jd: str
) -> AsyncIterator[str]:
    from app.services.llm_client import chat_stream, llm_configured

    parsed_resume = strip_resume_internal_keys(parsed_resume)
    if not llm_configured():
        payload = json.dumps(_mock_tailor(parsed_resume, jd_analysis))
        chunk = max(48, len(payload) // 20)
        for i in range(0, len(payload), chunk):
            yield payload[i : i + chunk]
        return
    try:
        system = (
            "Return ONLY JSON for ResumeSchema. No markdown. No fabrication. "
            "Real experience only from candidate_resume."
        )
        user_payload = json.dumps({"candidate_resume": parsed_resume, "jd_analysis": jd_analysis, "jd": raw_jd[:6000]})
        async for piece in chat_stream(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.4,
            max_tokens=8192,
        ):
            if piece:
                yield piece
    except Exception:
        yield json.dumps(_mock_tailor(parsed_resume, jd_analysis))
