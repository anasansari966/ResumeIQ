from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import Application, JobListing, Resume
from app.schemas import JSearchSmartIn, JSearchSmartOut, JobOut
from app.services.job_description_clean import clean_job_description
from app.services.job_match_preference import skills_from_jsearch_item
from app.services.job_page_enrich import fetch_description_from_apply_url
from app.services.job_seeds import match_score_resume
from app.services.jobspy_pipeline import smart_linkedin_fetch

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _to_job_out(j: JobListing, resume_json: Optional[dict] = None) -> JobOut:
    match_score = None
    matching_skills: list[str] = []
    missing_skills: list[str] = []
    if resume_json is not None:
        match_score, matching_skills, missing_skills = match_score_resume(j.skills or [], resume_json)
    return JobOut(
        id=j.id,
        source=j.source,
        title=j.title,
        company=j.company,
        location=j.location,
        description=j.description,
        salary_range=j.salary_range,
        job_type=j.job_type,
        remote=j.remote,
        skills=j.skills or [],
        posted_at=j.posted_at,
        apply_url=j.apply_url,
        match_score=match_score,
        matching_skills=matching_skills,
        missing_skills=missing_skills,
    )


async def _append_jobs_from_applications(
    session: AsyncSession,
    user_id: int,
    jobs: list[JobListing],
) -> list[JobListing]:
    """Include listings the user saved/applied to so the tracker can resolve titles."""
    seen = {j.id for j in jobs if j.id is not None}
    res = await session.exec(select(Application).where(Application.user_id == user_id))
    for app in res.all():
        jid = app.job_id
        if jid and jid not in seen:
            row = await session.get(JobListing, jid)
            if row:
                jobs.append(row)
                seen.add(jid)
    return jobs


@router.post("/jsearch/smart", response_model=JSearchSmartOut)
async def jsearch_smart_search(
    body: JSearchSmartIn,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Live jobs via JobSpy (boards in config) plus optional SerpAPI **web search** for company career / ATS apply links
    when ``SERPAPI_KEY`` is set. Search terms come from the resume or ``manual_query``.
    With a resume, listings are LLM short-listed for fit. Scraping is best-effort.
    """
    resume_json: Optional[dict] = None
    if body.resume_id is not None:
        r = await session.get(Resume, body.resume_id)
        if not r or r.user_id != user.id or r.deleted:
            raise HTTPException(404, "Resume not found")
        resume_json = r.parsed_json
    try:
        jobs, queries_used, msg, exp_years, exp_phrase, suggested_roles = await smart_linkedin_fetch(
            session,
            resume_json,
            body.manual_query,
            body.country,
            body.work_type,
            body.date_posted,
            body.page,
            body.num_pages,
        )
    except ValueError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Job search failed: {e}") from e
    return JSearchSmartOut(
        jobs=jobs,
        queries_used=queries_used,
        suggested_roles=suggested_roles,
        message=msg,
        experience_years_used=exp_years,
        experience_phrase=exp_phrase,
    )


@router.post("/listing/{job_id}/refresh-description", response_model=JobOut)
async def refresh_job_listing_description(
    job_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    resume_id: Optional[int] = Query(None),
):
    """
    Load or re-fetch job description from the listing's apply URL (LinkedIn job page, ATS / company site).
    Use when the JD panel is empty after board search.
    """
    row = await session.get(JobListing, job_id)
    if not row:
        raise HTTPException(404, "Job listing not found")
    url = (row.apply_url or "").strip()
    if not url:
        raise HTTPException(400, "This listing has no apply URL to fetch")

    raw = await fetch_description_from_apply_url(url)
    if not raw.strip():
        raise HTTPException(
            502,
            "Could not read a description from the job page (blocked, login wall, or unknown layout).",
        )

    cleaned = clean_job_description(raw)
    row.description = cleaned[:50_000]
    skills = skills_from_jsearch_item(
        {
            "job_title": row.title,
            "employer_name": row.company,
            "job_description": row.description,
            "job_location": row.location,
        }
    )
    if skills:
        row.skills = skills
    session.add(row)
    await session.commit()
    await session.refresh(row)

    resume_json: Optional[dict] = None
    if resume_id is not None:
        r = await session.get(Resume, resume_id)
        if r and r.user_id == user.id and not r.deleted:
            resume_json = r.parsed_json
    return _to_job_out(row, resume_json)


@router.get("/match", response_model=list[JobOut])
async def match_jobs(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    resume_id: Optional[int] = None,
    source: Optional[str] = None,
):
    resume_json: Optional[dict] = None
    if resume_id:
        r = await session.get(Resume, resume_id)
        if not r or r.user_id != user.id:
            raise HTTPException(404, "Resume not found")
        resume_json = r.parsed_json
    else:
        result = await session.exec(select(Resume).where(Resume.user_id == user.id, Resume.deleted == False))  # noqa: E712
        first = result.first()
        if first:
            resume_json = first.parsed_json

    res = await session.exec(select(JobListing))
    jobs = list(res.all())
    if (source or "").strip().lower() == "indeed":
        jobs = [j for j in jobs if (j.source or "").lower() == "indeed"]
    jobs = await _append_jobs_from_applications(session, user.id, jobs)
    out = [_to_job_out(j, resume_json) for j in jobs]
    out.sort(key=lambda x: (x.match_score or 0), reverse=True)
    return out


@router.get("/search", response_model=list[JobOut])
async def search_jobs(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = "",
    location: str = "",
    resume_id: Optional[int] = None,
    source: Optional[str] = None,
):
    resume_json: Optional[dict] = None
    if resume_id:
        r = await session.get(Resume, resume_id)
        if r and r.user_id == user.id:
            resume_json = r.parsed_json

    res = await session.exec(select(JobListing))
    jobs = list(res.all())
    if (source or "").strip().lower() == "indeed":
        jobs = [j for j in jobs if (j.source or "").lower() == "indeed"]
    ql = q.lower()
    ll = location.lower()
    filtered = []
    for j in jobs:
        hay = f"{j.title} {j.company} {j.description} {' '.join(j.skills or [])}".lower()
        if ql and ql not in hay:
            continue
        if ll and ll not in (j.location or "").lower():
            continue
        filtered.append(j)
    filtered = await _append_jobs_from_applications(session, user.id, filtered)
    out = [_to_job_out(j, resume_json) for j in filtered]
    out.sort(key=lambda x: (x.match_score or 0), reverse=True)
    return out
