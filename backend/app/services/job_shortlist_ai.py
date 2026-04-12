"""LLM filters scraped jobs to a preferred shortlist vs. full resume context."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.schemas import JobOut
from app.services.job_query_ai import _resume_brief

log = logging.getLogger(__name__)


async def shortlist_jobs_with_llm(
    resume_json: dict[str, Any],
    jobs: list[JobOut],
    *,
    pool_max: int,
    result_max: int,
) -> tuple[list[JobOut], str]:
    """
    Return jobs marked as strong fits (experience, education, skills, seniority).
    If OpenAI is unavailable or parsing fails, returns the first ``result_max`` heuristic-sorted jobs.
    """
    if not jobs:
        return [], ""

    if not (settings.openai_api_key or "").strip():
        return jobs, ""

    brief = _resume_brief(resume_json or {})
    if not (brief.get("roles") or brief.get("headline_summary") or brief.get("technical_skills")):
        return jobs, ""

    ranked = sorted(jobs, key=lambda j: (j.match_score or 0), reverse=True)
    pool = ranked[: max(1, min(pool_max, len(ranked)))]

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    job_rows = []
    for j in pool:
        desc = (j.description or "").strip().replace("\n", " ")
        job_rows.append(
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "skills": (j.skills or [])[:20],
                "remote": j.remote,
                "summary": desc[:1200],
            }
        )

    yrs = brief.get("estimated_years_experience")
    sys_msg = (
        "You are a senior recruiter. Compare the candidate profile to each job listing (title + summary). "
        f"Return ONLY valid JSON with key \"items\": an array of objects, one per job id, each with: "
        f"id (number, must match input), keep (boolean), fit_score (0-100 integer), "
        f"reason (one short sentence). "
        f"At most {result_max} entries may have keep true. "
        "CRITICAL — experience vs JD: Read each summary for minimum experience "
        "(e.g. '2+ years', '3–5 YOE', '5+ years', 'senior', 'staff', 'lead', 'principal', "
        "'fresher', 'entry level', 'new grad', 'intern'). "
        f"The model has candidate field estimated_years_experience={yrs!r} (None or 0 often means fresher/intern). "
        "If the candidate is a fresher or has ~0–1 years and the JD clearly expects 2+ or mid/senior level, set keep false "
        "unless the JD explicitly welcomes fresh graduates, interns, or 'training provided'. "
        "Also exclude wrong education level (e.g. PhD required vs no degree). "
        "Wrong domain or title seniority (Director vs junior) → keep false. Borderline → keep false."
    )
    user_obj = {
        "candidate": brief,
        "jobs": job_rows,
        "instruction": f"Prefer at most {result_max} keep=true entries; sort mentally by fit before deciding.",
    }
    user_msg = json.dumps(user_obj, ensure_ascii=False)

    try:
        resp = await client.chat.completions.create(
            model=settings.openai_parse_model,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1600,
        )
        raw = (resp.choices[0].message.content or "{}").strip()
        data = json.loads(raw)
        items = data.get("items")
        if not isinstance(items, list):
            raise ValueError("missing items array")

        pool_ids = {j.id for j in pool}
        by_id: dict[int, dict[str, Any]] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            jid = it.get("id")
            if jid is None:
                continue
            try:
                jid_i = int(jid)
            except (TypeError, ValueError):
                continue
            if jid_i not in pool_ids:
                continue
            by_id[jid_i] = {
                "keep": bool(it.get("keep")),
                "fit_score": _clamp_score(it.get("fit_score")),
                "reason": str(it.get("reason") or "").strip()[:400],
            }

        chosen: list[tuple[JobOut, dict[str, Any]]] = []
        job_map = {j.id: j for j in pool}
        for jid, meta in by_id.items():
            if not meta["keep"]:
                continue
            j = job_map.get(jid)
            if j:
                chosen.append((j, meta))

        chosen.sort(key=lambda x: (-x[1]["fit_score"], -(x[0].match_score or 0)))
        out: list[JobOut] = []
        for j, meta in chosen[:result_max]:
            out.append(
                j.model_copy(
                    update={
                        "match_score": float(meta["fit_score"]),
                        "fit_rationale": meta["reason"] or None,
                    }
                )
            )

        if not out:
            log.warning("LLM shortlist returned zero keeps; falling back to heuristic top")
            return ranked[:result_max], "AI shortlist: no strong fits — showing top heuristic matches instead."

        note = f"AI shortlist: {len(out)} preferred role(s) from {len(pool)} reviewed."
        return out, note
    except Exception as e:
        log.warning("shortlist_jobs_with_llm failed: %s", e)
        return jobs, ""


def _clamp_score(v: Any) -> int:
    try:
        x = int(float(v))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, x))
