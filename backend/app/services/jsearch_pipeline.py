"""Fetch live job listings via SerpAPI (Google Jobs), upsert JobListing rows, rank by resume fit (no JD)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.models_db import JobListing
from app.schemas import JobOut
from app.services.job_description_clean import clean_job_description
from app.services.job_match_preference import combined_preference_score, skills_from_jsearch_item
from app.services.job_query_ai import suggest_jsearch_queries
from app.services.resume_experience_years import experience_search_phrase, infer_total_experience_years
from app.services.serpapi_jobs_client import date_posted_to_chips, serpapi_google_jobs_search, to_serpapi_gl

# Google Jobs / SerpAPI can still surface cross-border listings; we post-filter when a country is selected.
JOB_LISTING_SOURCE = "serpapi"
ISO2_QUERY_LABEL: dict[str, str] = {
    "us": "United States",
    "gb": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "nl": "Netherlands",
    "se": "Sweden",
    "ch": "Switzerland",
    "ae": "United Arab Emirates",
    "sa": "Saudi Arabia",
    "in": "India",
    "sg": "Singapore",
    "jp": "Japan",
    "kr": "South Korea",
    "my": "Malaysia",
    "id": "Indonesia",
    "ph": "Philippines",
    "za": "South Africa",
    "br": "Brazil",
    "mx": "Mexico",
}

# Default metro for SerpAPI `location` ("City, Country") when user picks a country only.
ISO2_DEFAULT_CITY: dict[str, str] = {
    "in": "Delhi",
    "us": "New York",
    "gb": "London",
    "ca": "Toronto",
    "au": "Sydney",
    "de": "Berlin",
    "fr": "Paris",
    "nl": "Amsterdam",
    "se": "Stockholm",
    "ch": "Zurich",
    "ae": "Dubai",
    "sa": "Riyadh",
    "sg": "Singapore",
    "jp": "Tokyo",
    "kr": "Seoul",
    "my": "Kuala Lumpur",
    "id": "Jakarta",
    "ph": "Manila",
    "za": "Johannesburg",
    "br": "São Paulo",
    "mx": "Mexico City",
}

COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    "india": "in",
    "united states": "us",
    "usa": "us",
    "u.s.": "us",
    "u.s.a.": "us",
    "america": "us",
    "united kingdom": "gb",
    "uk": "gb",
    "great britain": "gb",
    "canada": "ca",
    "australia": "au",
    "germany": "de",
    "france": "fr",
    "netherlands": "nl",
    "sweden": "se",
    "switzerland": "ch",
    "united arab emirates": "ae",
    "uae": "ae",
    "saudi arabia": "sa",
    "singapore": "sg",
    "japan": "jp",
    "south korea": "kr",
    "korea": "kr",
    "malaysia": "my",
    "indonesia": "id",
    "philippines": "ph",
    "south africa": "za",
    "brazil": "br",
    "mexico": "mx",
}

# Google Jobs India listings often end with a state/UT name, not "India" — map those to ``in``.
_INDIAN_ADMIN_DIVISIONS = (
    "andhra pradesh",
    "arunachal pradesh",
    "assam",
    "bihar",
    "chhattisgarh",
    "goa",
    "gujarat",
    "haryana",
    "himachal pradesh",
    "jharkhand",
    "karnataka",
    "kerala",
    "madhya pradesh",
    "maharashtra",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "odisha",
    "orissa",
    "punjab",
    "rajasthan",
    "sikkim",
    "tamil nadu",
    "telangana",
    "tripura",
    "uttar pradesh",
    "uttarakhand",
    "west bengal",
    "delhi",
    "jammu and kashmir",
    "ladakh",
    "chandigarh",
    "puducherry",
    "dadra and nagar haveli",
    "daman and diu",
    "lakshadweep",
    "andaman and nicobar islands",
)
for _adm in _INDIAN_ADMIN_DIVISIONS:
    COUNTRY_NAME_TO_ISO2[_adm] = "in"


def _manual_to_short_job_title(text: str) -> str:
    """Strip experience suffixes / ``jobs`` so ``q`` stays a short title for Google Jobs."""
    s = (text or "").strip()
    s = re.sub(r"\s+\d+\s*([+\-]\s*\d+)?\s*(yr|yrs|year|years)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\bjobs?\s*$", "", s, flags=re.I).strip()
    words = s.split()
    if len(words) > 8:
        s = " ".join(words[:8])
    return s or "Jobs"


def _title_from_verbose_query(q: str) -> str:
    s = (q or "").strip()
    s = re.sub(r"\s+\d+\s*([+\-]\s*\d+)?\s*(yr|yrs|year|years)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\bjobs?\s*$", "", s, flags=re.I).strip()
    words = s.split()
    if len(words) > 6:
        s = " ".join(words[:6])
    return s or "Jobs"


def _build_serpapi_location(loc_phrase: str, qcountry: str) -> str:
    """SerpAPI expects ``City, Country`` when possible (e.g. ``Delhi, India``)."""
    lp = (loc_phrase or "").strip()
    geo = ISO2_QUERY_LABEL.get(qcountry, "") if qcountry else ""
    if "," in lp:
        return lp
    if lp and geo:
        return f"{lp}, {geo}"
    if lp:
        return lp
    if qcountry:
        city = ISO2_DEFAULT_CITY.get(qcountry, "")
        if city and geo:
            return f"{city}, {geo}"
        return geo or ""
    return ""


def _iso2_from_jsearch_item(item: dict[str, Any]) -> str | None:
    raw = (item.get("job_country") or "").strip()
    if not raw:
        return None
    r = raw.lower()
    if len(r) == 2 and r.isalpha():
        return r
    return COUNTRY_NAME_TO_ISO2.get(r)


def _iso2_from_location_tail(item: dict[str, Any]) -> str | None:
    loc = _location_str(item)
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if not parts:
        return None
    tail = parts[-1].lower()
    if len(tail) == 2 and tail.isalpha():
        return tail
    return COUNTRY_NAME_TO_ISO2.get(tail)


def _item_iso2_best(item: dict[str, Any]) -> str | None:
    return _iso2_from_jsearch_item(item) or _iso2_from_location_tail(item)


def _item_matches_selected_country(item: dict[str, Any], qcountry: str) -> bool:
    if not qcountry:
        return True
    got = _item_iso2_best(item)
    if got is not None:
        return got == qcountry
    loc = _location_str(item).lower()
    hint = ISO2_QUERY_LABEL.get(qcountry, "").lower()
    if hint and hint in loc:
        return True
    # No reliable geo signal — drop to avoid US noise when a country filter is active.
    return False


def _parse_posted_at(item: dict[str, Any]) -> datetime:
    s = item.get("job_posted_at_datetime_utc") or item.get("job_posted_at") or ""
    if not s:
        return datetime.utcnow()
    try:
        s2 = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.utcnow()


def _location_str(item: dict[str, Any]) -> str:
    city = (item.get("job_city") or "").strip()
    state = (item.get("job_state") or "").strip()
    country = (item.get("job_country") or "").strip()
    parts = [p for p in [city, state, country] if p]
    if parts:
        return ", ".join(parts)[:500]
    loc = (item.get("job_location") or item.get("job_city_state") or "").strip()
    if loc:
        return loc[:500]
    return "Remote"


def _employment_type(item: dict[str, Any]) -> str:
    et = item.get("job_employment_types") or item.get("job_employment_type")
    if isinstance(et, list) and et:
        raw = str(et[0])
    elif isinstance(et, str):
        raw = et
    else:
        return "full-time"
    raw = raw.upper().replace("_", "-")
    if "PART" in raw:
        return "part-time"
    if "CONTRACT" in raw:
        return "contract"
    if "INTERN" in raw:
        return "internship"
    return "full-time"


def _remote_str(item: dict[str, Any]) -> str:
    if item.get("job_is_remote") is True:
        return "remote"
    loc = _location_str(item).lower()
    title = (item.get("job_title") or "").lower()
    if "remote" in loc or "work from home" in loc or "wfh" in loc:
        return "remote"
    if any(x in title for x in ("remote", "wfh", "work from home")):
        return "remote"
    blob = (item.get("job_description") or "")[:2000].lower()
    if any(
        x in blob
        for x in (
            "work from home",
            "fully remote",
            "100% remote",
            "remote role",
            "remote position",
            "remote work",
        )
    ):
        return "remote"
    return "hybrid"


def _salary_str(item: dict[str, Any]) -> str | None:
    lo = item.get("job_min_salary") or item.get("job_salary")
    hi = item.get("job_max_salary")
    if lo and hi:
        return f"{lo} – {hi}"
    if lo:
        return str(lo)
    return item.get("job_salary_period") or None


def _apply_url(item: dict[str, Any]) -> str | None:
    u = item.get("job_apply_link")
    if u and not isinstance(u, bool):
        return str(u)[:2000]
    opts = item.get("apply_options") or []
    if isinstance(opts, list):
        for o in opts:
            if isinstance(o, dict):
                link = o.get("apply_link") or o.get("publisher_apply_link") or o.get("url") or o.get("link")
                if link:
                    return str(link)[:2000]
    return None


def _payload_job_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("jobs", "data", "results", "job_list"):
        raw = payload.get(key)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    return []


def listing_fields_from_normalized(item: dict[str, Any], source: str) -> dict[str, Any]:
    jid = str(item.get("job_id") or "").strip()
    if not jid:
        raise ValueError("job item missing job_id")
    title = (item.get("job_title") or "Role").strip()[:500] or "Role"
    company = (item.get("employer_name") or "Company").strip()[:300] or "Company"
    desc = clean_job_description(str(item.get("job_description") or ""))
    apply_url = _apply_url(item)
    skills = skills_from_jsearch_item({**item, "job_description": desc})
    return {
        "source": source,
        "external_id": jid[:200],
        "title": title,
        "company": company,
        "location": _location_str(item),
        "description": desc if desc else "",
        "salary_range": _salary_str(item),
        "job_type": _employment_type(item),
        "remote": _remote_str(item),
        "skills": skills,
        "posted_at": _parse_posted_at(item),
        "apply_url": apply_url,
    }


async def upsert_job_listing(session: AsyncSession, item: dict[str, Any], source: str) -> JobListing:
    fields = listing_fields_from_normalized(item, source)
    ext = fields["external_id"]
    res = await session.exec(select(JobListing).where(JobListing.external_id == ext, JobListing.source == source))
    existing = res.first()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        session.add(existing)
        await session.flush()
        return existing
    row = JobListing(**fields)
    session.add(row)
    await session.flush()
    return row


async def smart_jsearch_fetch(
    session: AsyncSession,
    resume_json: dict[str, Any] | None,
    manual_query: str,
    country_override: str,
    work_type: str,
    date_posted: str,
    page: int,
    num_pages: int,
) -> tuple[list[JobOut], list[str], str, int | None, str, list[str]]:
    """
    Returns (jobs, queries_used, message, inferred_experience_years, experience_phrase, suggested_roles).
    """
    resume_json = resume_json or {}
    queries_used: list[str] = []
    fetch_errors: list[str] = []
    years = infer_total_experience_years(resume_json) if resume_json else None
    phrase = experience_search_phrase(years)
    suggested_roles: list[str] = []

    if manual_query.strip():
        base_manual = manual_query.strip()
        mq = base_manual
        if phrase and phrase.lower() not in mq.lower():
            mq = f"{mq} {phrase}".strip()
        short_title = _manual_to_short_job_title(base_manual)
        plan = {
            "queries": [mq],
            "country": "",
            "location_phrase": "",
            "role_titles": [short_title],
        }
        msg = "Manual search (SerpAPI: short job title + location / chips)."
    else:
        plan = await suggest_jsearch_queries(resume_json)
        qplan_src = str(plan.pop("query_plan_source", "") or "")
        suggested_roles = list(plan.get("role_titles") or [])
        if not isinstance(suggested_roles, list):
            suggested_roles = []
        suggested_roles = [str(x).strip() for x in suggested_roles if str(x).strip()][:10]
        if years is not None:
            msg = f"Role-based Google Jobs (SerpAPI) from your resume (~{years} yr experience inferred)."
        else:
            msg = "Role-based Google Jobs (SerpAPI) queries from your resume."
        if qplan_src == "openai":
            msg = f"{msg} Role titles from OpenAI ({settings.openai_model})."
        elif qplan_src in ("heuristic_llm_error", "heuristic_empty_llm_queries"):
            msg = f"{msg} OpenAI title suggestion unavailable; using built-in templates."
        elif qplan_src == "heuristic" and not (settings.openai_api_key or "").strip():
            msg = f"{msg} Optional: set OPENAI_API_KEY for AI-suggested titles from your resume."

    if settings.serpapi_dry_run:
        msg = f"{msg} SERPAPI_DRY_RUN=true: sample listing only; no quota used."

    raw_ov = (country_override or "").strip().lower()
    country_locked = bool(raw_ov)
    qcountry = raw_ov[:2] if country_locked else ""
    wtype = (work_type or "all").strip().lower()
    if wtype not in {"all", "remote", "on-site"}:
        wtype = "all"
    raw_queries = plan.get("queries") or []
    if not isinstance(raw_queries, list):
        raw_queries = []
    raw_queries = [str(q).strip() for q in raw_queries if str(q).strip()][:5]

    role_titles = [str(t).strip() for t in (plan.get("role_titles") or []) if str(t).strip()]
    loc_hint = _build_serpapi_location((plan.get("location_phrase") or "").strip(), qcountry)

    max_q = max(1, min(5, int(settings.serpapi_max_queries_per_search)))
    effective_pages = max(1, min(int(num_pages or 1), int(settings.serpapi_max_pages_per_query)))
    chips = date_posted_to_chips(date_posted)
    _ = page  # API compatibility (JSearch paging)

    seen_items: dict[str, dict[str, Any]] = {}
    for i in range(max_q):
        if i < len(role_titles):
            q_short = role_titles[i]
        elif i < len(raw_queries):
            q_short = _title_from_verbose_query(raw_queries[i])
        elif role_titles:
            q_short = role_titles[i % len(role_titles)]
        elif raw_queries:
            q_short = _title_from_verbose_query(raw_queries[i % len(raw_queries)])
        else:
            break
        if wtype == "remote" and "remote" not in q_short.lower():
            q_short = f"{q_short} remote"
        elif wtype == "on-site" and "on-site" not in q_short.lower() and "onsite" not in q_short.lower():
            q_short = f"{q_short} on-site"
        q_label = q_short + (f" · {loc_hint}" if loc_hint else " · global")
        if chips:
            q_label = f"{q_label} · {chips}"
        queries_used.append(q_label)
        try:
            payload = await serpapi_google_jobs_search(
                q_short,
                country_gl=to_serpapi_gl(qcountry) if qcountry else "",
                location=loc_hint,
                chips=chips,
                num_pages=effective_pages,
            )
        except Exception as e:
            fetch_errors.append(f"{q_short[:48]}… → {e}")
            continue
        for it in _payload_job_list(payload):
            if not _item_matches_selected_country(it, qcountry):
                continue
            jid = str(it.get("job_id") or "").strip()
            if jid:
                seen_items[jid] = it

    if not seen_items:
        err_tail = ""
        if fetch_errors:
            err_tail = " API details: " + " | ".join(fetch_errors[:3])
            msg_empty = (
                "No job results. Set SERPAPI_KEY, check SerpAPI quota/dashboard, "
                "or use SERPAPI_DRY_RUN=true to test UI without API calls."
            )
        elif queries_used:
            msg_empty = (
                "No listings matched this search. Try posted date “All time”, work type “All”, "
                "or broader titles/locations. If you use a date filter, Google Jobs sometimes returns "
                "nothing until results are refetched without that filter."
            )
        else:
            msg_empty = (
                "No job results. Set SERPAPI_KEY, check SerpAPI quota/dashboard, "
                "or use SERPAPI_DRY_RUN=true to test UI without API calls."
            )
        return ([], queries_used, msg_empty + err_tail, years, phrase, suggested_roles)

    merged: list[tuple[dict[str, Any], JobListing]] = []
    for item in seen_items.values():
        try:
            row = await upsert_job_listing(session, item, JOB_LISTING_SOURCE)
            if wtype == "remote" and row.remote != "remote":
                blob = f"{row.title} {row.location} {(row.description or '')[:2500]}".lower()
                if not any(
                    x in blob
                    for x in (
                        "remote",
                        "work from home",
                        "wfh",
                        "work-from-home",
                        "fully remote",
                        "hybrid",
                    )
                ):
                    continue
            if wtype == "on-site" and row.remote == "remote":
                continue
            merged.append((item, row))
        except Exception:
            continue

    await session.commit()

    out: list[JobOut] = []
    for item, row in merged:
        await session.refresh(row)
        desc_clean = str(row.description or "")
        skills = row.skills or skills_from_jsearch_item({**item, "job_description": desc_clean})
        score, matching, missing = combined_preference_score(
            skills,
            desc_clean,
            str(row.title or item.get("job_title") or ""),
            resume_json,
            None,
        )
        out.append(
            JobOut(
                id=row.id,
                source=row.source,
                title=row.title,
                company=row.company,
                location=row.location,
                description=(row.description or "")[:50_000],
                salary_range=row.salary_range,
                job_type=row.job_type,
                remote=row.remote,
                skills=row.skills or skills,
                posted_at=row.posted_at,
                apply_url=row.apply_url,
                match_score=score,
                matching_skills=matching,
                missing_skills=missing,
            )
        )

    out.sort(key=lambda x: (x.match_score or 0), reverse=True)
    return out, queries_used, msg, years, phrase, suggested_roles
