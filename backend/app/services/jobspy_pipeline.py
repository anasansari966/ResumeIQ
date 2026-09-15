"""Live jobs from multiple JobSpy platforms plus company/ATS career pages.

Scraped jobs are optionally short-listed by an LLM against resume experience, skills, and role fit.
Monster is not supported by JobSpy.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.schemas import JobOut
from app.models_db import JobListing
from app.services.job_eligibility import analyze_job_eligibility
from app.services.job_description_clean import clean_job_description
from app.services.job_match_preference import skills_from_jsearch_item
from app.services.job_page_enrich import fetch_description_from_apply_url
from app.services.job_query_ai import suggest_jsearch_queries
from app.services.jsearch_pipeline import (
    ISO2_QUERY_LABEL,
    _apply_url,
    _item_matches_selected_country,
    _manual_to_short_job_title,
    _title_from_verbose_query,
    upsert_job_listing,
)
from app.services.serpapi_web_jobs import fetch_career_hits_from_web_search
from app.services.resume_experience_years import experience_search_phrase, infer_total_experience_years
from app.services.job_shortlist_ai import shortlist_jobs_with_llm

log = logging.getLogger(__name__)

# Google Jobs often surfaces roles hosted on employer / ATS career pages (Greenhouse, Lever, etc.).
_BOARDS_DEFAULT: tuple[str, ...] = ("linkedin", "indeed", "glassdoor", "google")
_ALLOWED_BOARDS = frozenset({"linkedin", "indeed", "glassdoor", "zip_recruiter", "google", "bayt", "bdjobs"})
_BOARD_LABELS = {
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "zip_recruiter": "ZipRecruiter",
    "google": "Google Jobs",
    "bayt": "Bayt",
    "bdjobs": "BDJobs",
}

_INDEED_COUNTRY: dict[str, str] = {
    "us": "USA",
    "in": "India",
    "gb": "UK",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "nl": "Netherlands",
    "se": "Sweden",
    "ch": "Switzerland",
    "ae": "United Arab Emirates",
    "sa": "Saudi Arabia",
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


def _parse_boards_setting() -> tuple[str, ...]:
    raw = (getattr(settings, "jobspy_sites", None) or "").strip()
    if not raw:
        return _BOARDS_DEFAULT
    parts = [p.strip().lower() for p in re.split(r"[,\s]+", raw) if p.strip()]
    out = [p for p in parts if p in _ALLOWED_BOARDS]
    return tuple(out) if out else _BOARDS_DEFAULT


def _boards_label(boards: tuple[str, ...]) -> str:
    return " · ".join(_BOARD_LABELS.get(board, board.replace("_", " ").title()) for board in boards)


def _jobspy_scrape_location(qcountry: str) -> str:
    qc = (qcountry or "").strip().lower()[:2]
    if not qc:
        return "Worldwide"
    return ISO2_QUERY_LABEL.get(qc) or "Worldwide"


def _indeed_country_label(qcountry: str) -> str:
    qc = (qcountry or "").strip().lower()[:2]
    if not qc:
        return "USA"
    return _INDEED_COUNTRY.get(qc, "USA")


def _date_posted_to_hours_old(date_posted: str) -> int:
    x = (date_posted or "all").strip().lower().replace("_", "").replace(" ", "")
    if x in ("today",):
        return 24
    if x in ("3days", "last3days"):
        return 72
    if x in ("week", "lastweek"):
        return 168
    if x in ("month", "lastmonth"):
        return 720
    return 8760


def _board_source_from_row(row: Any) -> str:
    s = _str_cell(row, "site").lower().replace(" ", "_")
    if s in _ALLOWED_BOARDS:
        return s
    return "jobspy"


def _jobspy_row_to_item(row: Any) -> dict[str, Any] | None:
    if not hasattr(row, "get"):
        return None
    url = _str_cell(row, "job_url")
    title = _str_cell(row, "title")
    company = _str_cell(row, "company")
    if not title and not company:
        return None
    if url:
        jid = hashlib.sha256(url.encode("utf-8")).hexdigest()[:40]
    else:
        src = _board_source_from_row(row)
        jid = hashlib.sha256(f"{src}|{title}|{company}".encode()).hexdigest()[:40]

    loc = _str_cell(row, "location")
    desc = _str_cell(row, "description")
    job_type_raw = _str_cell(row, "job_type") or "full-time"
    salary = _str_cell(row, "salary")
    if not salary:
        lo = row.get("min_amount")
        hi = row.get("max_amount")
        if lo is not None and hi is not None and not (isinstance(lo, float) and pd.isna(lo)):
            salary = f"{lo} – {hi}"
        elif lo is not None and not (isinstance(lo, float) and pd.isna(lo)):
            salary = str(lo)

    date_val = row.get("date_posted")
    posted_s = ""
    if date_val is not None and not (isinstance(date_val, float) and pd.isna(date_val)):
        if hasattr(date_val, "isoformat"):
            posted_s = date_val.isoformat()
        else:
            posted_s = str(date_val)

    loc_l = loc.lower()
    remote_guess = "remote" in loc_l or "remote" in title.lower()
    return {
        "job_id": jid,
        "job_title": title or "Role",
        "employer_name": company or "Company",
        "job_description": desc,
        "job_location": loc,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_apply_link": url or None,
        "apply_options": [{"apply_link": url}] if url else [],
        "job_is_remote": remote_guess,
        "job_employment_types": [job_type_raw] if job_type_raw else [],
        "job_posted_at": posted_s,
        "job_posted_at_datetime_utc": posted_s,
        "job_min_salary": None,
        "job_max_salary": None,
        "job_salary": salary or None,
    }


def _str_cell(row: Any, key: str) -> str:
    v = row.get(key) if hasattr(row, "get") else None
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _linkedin_hours_old_for_jobspy(hours_old: int) -> int | None:
    """
    JobSpy passes hours_old to LinkedIn as f_TPR=r{hours_old * 3600}.
    Very large values (e.g. 8760h → r31536000) reliably trigger HTTP 500 on the guest API.
    Omit the parameter so LinkedIn serves the default any-time listing.
    """
    ho = max(1, int(hours_old or 1))
    cutoff = int(getattr(settings, "jobspy_linkedin_omit_time_filter_hours_gte", 7200) or 7200)
    if ho >= cutoff:
        return None
    return ho


def _scrape_one_site_sync(
    site: str,
    *,
    search_term: str,
    location: str,
    per_site: int,
    hours_old: int,
    indeed_country: str,
) -> pd.DataFrame | None:
    from jobspy import scrape_jobs

    ho = max(1, min(int(hours_old or 720), 8760))
    li_hours = _linkedin_hours_old_for_jobspy(ho) if site == "linkedin" else ho

    def _call(effective_hours: int | None) -> pd.DataFrame | None:
        kwargs: dict[str, Any] = {
            "site_name": [site],
            "search_term": search_term,
            "location": location,
            "results_wanted": per_site,
        }
        if effective_hours is not None:
            kwargs["hours_old"] = effective_hours
        if site == "linkedin" and getattr(settings, "jobspy_linkedin_fetch_descriptions", False):
            kwargs["linkedin_fetch_description"] = True
        if site == "indeed":
            kwargs["country_indeed"] = indeed_country
        return scrape_jobs(**kwargs)

    try:
        df = _call(li_hours)
        if df is not None and not df.empty:
            return df
        # Guest LinkedIn often errors or returns empty when f_TPR is set; retry without time filter.
        if site == "linkedin" and li_hours is not None:
            log.info(
                "LinkedIn returned no rows with time filter (hours_old=%s); retrying any-time search.",
                li_hours,
            )
            df = _call(None)
            if df is not None and not df.empty:
                return df
    except Exception as e:
        if site == "linkedin" and li_hours is not None:
            log.warning("JobSpy linkedin scrape failed (%s); retry any-time.", e)
            try:
                df = _call(None)
                if df is not None and not df.empty:
                    return df
            except Exception as e2:
                log.warning("JobSpy linkedin retry failed: %s", e2)
        else:
            log.warning("JobSpy %s scrape failed: %s", site, e)
    return None


def _scrape_job_boards_sync(
    search_term: str,
    *,
    location: str,
    hours_old: int,
    results_cap: int,
    indeed_country: str,
    boards: tuple[str, ...],
) -> pd.DataFrame:
    loc = (location or "").strip() or "Worldwide"
    n_boards = max(1, len(boards))
    per_site = max(4, min(28, max(results_cap // n_boards, 8)))
    ho = max(1, min(int(hours_old or 720), 8760))
    frames: list[pd.DataFrame] = []

    workers = min(8, max(2, len(boards)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                _scrape_one_site_sync,
                site,
                search_term=search_term,
                location=loc,
                per_site=per_site,
                hours_old=ho,
                indeed_country=indeed_country,
            ): site
            for site in boards
        }
        for fut in as_completed(futs):
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception as e:
                log.warning("JobSpy board task failed: %s", e)

    # Align columns so mixed board schemas concat cleanly (avoids pandas FutureWarning on dtype merge).
    nonempty = [f for f in frames if f is not None and not f.empty]
    if not nonempty:
        return pd.DataFrame()
    if len(nonempty) == 1:
        out = nonempty[0].reset_index(drop=True)
    else:
        cols: list[str] = sorted({c for f in nonempty for c in f.columns})
        aligned = [f.reindex(columns=cols) for f in nonempty]
        out = pd.concat(aligned, ignore_index=True, sort=False)
    if "job_url" in out.columns and out["job_url"].notna().any():
        out = out.drop_duplicates(subset=["job_url"], keep="first")
    elif "title" in out.columns and "company" in out.columns:
        out = out.drop_duplicates(subset=["title", "company", "site"], keep="first")
    return out.head(min(len(out), max(results_cap, per_site * n_boards)))


async def smart_jobspy_fetch(
    session: AsyncSession,
    resume_json: dict[str, Any] | None,
    manual_query: str,
    country_override: str,
    work_type: str,
    date_posted: str,
    page: int,
    num_pages: int,
    location_override: str = "",
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

    raw_ov = (country_override or "").strip().lower()
    country_locked = bool(raw_ov)
    qcountry = raw_ov[:2] if country_locked else ""
    scrape_location = _jobspy_scrape_location(qcountry)
    indeed_country = _indeed_country_label(qcountry)
    boards = _parse_boards_setting()
    boards_label = _boards_label(boards)

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
        msg = f"JobSpy ({boards_label}) · {scrape_location} — manual search."
    else:
        plan = await suggest_jsearch_queries(resume_json)
        plan.pop("query_plan_source", None)
        suggested_roles = list(plan.get("role_titles") or [])
        if not isinstance(suggested_roles, list):
            suggested_roles = []
        suggested_roles = [str(x).strip() for x in suggested_roles if str(x).strip()][:10]
        if years is not None:
            msg = (
                f"JobSpy ({boards_label}) · {scrape_location} — AI/heuristic job titles from your resume "
                f"(~{years} yr); each title is searched with your skills and experience level."
            )
        else:
            msg = (
                f"JobSpy ({boards_label}) · {scrape_location} — AI/heuristic job titles from your resume; "
                f"each title is searched with your skills."
            )

    if not country_locked:
        planned_country = str(plan.get("country") or "").strip().lower()[:2]
        if planned_country:
            qcountry = planned_country
    planned_location = str(plan.get("location_phrase") or "").strip()
    scrape_location = (location_override or "").strip() or planned_location or _jobspy_scrape_location(qcountry)
    indeed_country = _indeed_country_label(qcountry)
    if manual_query.strip():
        msg = f"Manual job search in {scrape_location}, filtered against the selected resume."
    elif years is not None:
        msg = (
            f"Resume-based role search in {scrape_location} using approximately {years} years of experience. "
            "Each listing is checked against experience, role alignment, and skills."
        )
    else:
        msg = (
            f"Resume-based role search in {scrape_location}. "
            "Each listing is checked against role alignment and skills."
        )

    wtype = (work_type or "all").strip().lower()
    if wtype not in {"all", "remote", "on-site"}:
        wtype = "all"

    raw_queries = plan.get("queries") or []
    if not isinstance(raw_queries, list):
        raw_queries = []
    raw_queries = [str(q).strip() for q in raw_queries if str(q).strip()][:8]

    role_titles = [str(t).strip() for t in (plan.get("role_titles") or []) if str(t).strip()]

    hours_old = _date_posted_to_hours_old(date_posted)
    max_q = max(1, min(8, int(settings.linkedin_jobspy_max_queries or 6)))
    # One combined JobSpy call per manual text; resume-driven search fans out across many AI/heuristic roles.
    if manual_query.strip():
        max_q = 1
    else:
        # Only expose generated roles that are actually sent to the job platforms.
        suggested_roles = suggested_roles[:max_q]
    per_q = max(5, min(60, int(settings.linkedin_jobspy_results_per_query)))
    results_cap = min(120, per_q * max(1, int(num_pages or 1)))
    _ = page

    seen_items: dict[str, dict[str, Any]] = {}
    board_sources: dict[str, str] = {}

    query_strings: list[str] = []
    for i in range(max_q):
        # Prefer full resume-aware queries (skills + experience hint) when the AI/heuristic plan provides them.
        if i < len(raw_queries):
            q_short = raw_queries[i]
        elif i < len(role_titles):
            q_short = role_titles[i]
            if phrase and phrase.lower() not in q_short.lower():
                q_short = f"{q_short} {phrase}".strip()
        elif role_titles:
            q_short = role_titles[i % len(role_titles)]
            if phrase and phrase.lower() not in q_short.lower():
                q_short = f"{q_short} {phrase}".strip()
        elif raw_queries:
            q_short = raw_queries[i % len(raw_queries)]
        else:
            break
        if wtype == "remote" and "remote" not in q_short.lower():
            q_short = f"{q_short} remote"
        elif wtype == "on-site" and "on-site" not in q_short.lower() and "onsite" not in q_short.lower():
            q_short = f"{q_short} on-site"

        age_label = {24: "24h", 72: "3d", 168: "7d", 720: "30d"}.get(hours_old, f"{hours_old}h")
        queries_used.append(f"{q_short} · {scrape_location} · {age_label} · {boards_label}")
        query_strings.append(q_short)

    async def _one_scrape(q_short: str) -> pd.DataFrame | None:
        try:
            return await asyncio.to_thread(
                _scrape_job_boards_sync,
                q_short,
                location=scrape_location,
                hours_old=hours_old,
                results_cap=results_cap,
                indeed_country=indeed_country,
                boards=boards,
            )
        except Exception as e:
            log.warning("JobSpy batch failed for %r: %s", q_short, e)
            fetch_errors.append(f"{q_short[:40]}… → {e}")
            return None

    dfs_list, web_pack = await asyncio.gather(
        asyncio.gather(*[_one_scrape(q) for q in query_strings]),
        fetch_career_hits_from_web_search(
            query_strings,
            location_label=scrape_location,
            qcountry=qcountry,
        ),
    )
    web_items, web_labels = web_pack

    for df in dfs_list:
        if df is None or df.empty:
            continue
        for _, prow in df.iterrows():
            it = _jobspy_row_to_item(prow)
            if not it:
                continue
            if not _item_matches_selected_country(it, qcountry):
                continue
            jid = str(it.get("job_id") or "").strip()
            if jid:
                seen_items[jid] = it
                board_sources[jid] = _board_source_from_row(prow)

    apply_seen = {_apply_url(it) for it in seen_items.values() if _apply_url(it)}
    for it in web_items:
        if not _item_matches_selected_country(it, qcountry):
            continue
        au = _apply_url(it)
        if au and au in apply_seen:
            continue
        jid = str(it.get("job_id") or "").strip()
        if not jid or jid in seen_items:
            continue
        seen_items[jid] = it
        board_sources[jid] = "serpapi_web"
        if au:
            apply_seen.add(au)

    if web_labels:
        queries_used.extend(web_labels)
        msg = f"{msg} Includes company career / ATS pages from Google web search (SerpAPI) when the API key is set."

    if not seen_items:
        err_tail = ""
        if fetch_errors:
            err_tail = " Details: " + " | ".join(fetch_errors[:2])
        if queries_used:
            msg_empty = (
                "No listings returned from job boards (blocking, captchas, or filters). "
                "Try “Any time”, “All” work type, or a broader title."
            )
        else:
            msg_empty = "No search terms — add a resume or use custom search text."
        return ([], queries_used, msg_empty + err_tail, years, phrase, suggested_roles)

    merged: list[tuple[dict[str, Any], JobListing]] = []
    for jid, item in seen_items.items():
        src = board_sources.get(jid) or "jobspy"
        try:
            row = await upsert_job_listing(session, item, src)
            merged.append((item, row))
        except Exception:
            continue

    await session.commit()

    # Job-board rows usually contain a full JD. Career/ATS search hits and some
    # board rows contain only a snippet; load those pages before eligibility so
    # required experience is compared against the resume, not against a teaser.
    enrich_candidates = [
        row
        for _, row in merged
        if row.apply_url
        and (
            row.source == "serpapi_web"
            or len((row.description or "").strip()) < 450
        )
    ][:18]
    if enrich_candidates:
        semaphore = asyncio.Semaphore(4)

        async def _load_full_jd(row: JobListing) -> tuple[JobListing, str]:
            async with semaphore:
                try:
                    raw = await fetch_description_from_apply_url(row.apply_url or "")
                    return row, clean_job_description(raw)[:50_000]
                except Exception as exc:
                    log.info("Could not enrich JD for job %s: %s", row.id, exc)
                    return row, ""

        enriched = await asyncio.gather(*[_load_full_jd(row) for row in enrich_candidates])
        changed = False
        for row, full_jd in enriched:
            if full_jd and len(full_jd) > len((row.description or "").strip()):
                row.description = full_jd
                session.add(row)
                changed = True
        if changed:
            await session.commit()

    out: list[JobOut] = []
    for item, row in merged:
        await session.refresh(row)
        desc_clean = str(row.description or "")
        skills = row.skills or skills_from_jsearch_item({**item, "job_description": desc_clean})
        analysis = analyze_job_eligibility(
            title=str(row.title or item.get("job_title") or ""),
            description=desc_clean,
            job_skills=skills,
            resume_json=resume_json,
        )
        if resume_json and not analysis.eligible:
            continue
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
                match_score=analysis.score,
                matching_skills=analysis.matching_skills,
                missing_skills=analysis.missing_skills,
                fit_rationale=analysis.rationale,
                is_eligible=analysis.eligible if resume_json else None,
                eligibility_reasons=analysis.reasons,
                candidate_experience_years=analysis.candidate_years,
                required_experience_years=analysis.required_years,
            )
        )

    out.sort(key=lambda x: (x.match_score or 0), reverse=True)

    if resume_json and out:
        pool = int(getattr(settings, "jobspy_shortlist_llm_pool", 45) or 45)
        cap = int(getattr(settings, "jobspy_shortlist_max_results", 18) or 18)
        try:
            out, short_note = await shortlist_jobs_with_llm(
                resume_json,
                out,
                pool_max=pool,
                result_max=cap,
            )
            if short_note:
                msg = f"{msg} {short_note}"
        except Exception as e:
            log.warning("Job shortlist step skipped: %s", e)

    if resume_json:
        source_count = len({job.source for job in out if job.source})
        msg = (
            f"{msg} Compared resume experience with each extracted job description. "
            f"{len(out)} eligible match{'es' if len(out) != 1 else ''} from "
            f"{source_count} platform{'s' if source_count != 1 else ''} shown."
        )
    return out, queries_used, msg, years, phrase, suggested_roles


# Back-compat alias
smart_linkedin_fetch = smart_jobspy_fetch
