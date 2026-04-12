"""SerpAPI Google Jobs (`engine=google_jobs`).

Uses the official ``serpapi.GoogleSearch`` client (same parameters as https://serpapi.com/google-jobs-api):
short ``q`` (job title), ``location`` as ``City, Country``, ``gl`` / ``hl``, optional ``chips`` (e.g. ``date_posted:week``).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

# SerpAPI ``gl`` uses ``uk`` for United Kingdom, not ``gb``.
ISO2_TO_SERPAPI_GL: dict[str, str] = {
    "gb": "uk",
}


def _serpapi_key() -> str:
    k = (getattr(settings, "serpapi_key", None) or "").strip()
    if k:
        return k
    return (os.environ.get("SERPAPI_KEY") or os.environ.get("serpapi_key") or "").strip()


def to_serpapi_gl(iso2: str) -> str:
    c = (iso2 or "").strip().lower()
    if len(c) == 2:
        return ISO2_TO_SERPAPI_GL.get(c, c)
    return c


def date_posted_to_chips(date_posted: str) -> str | None:
    """Map API ``date_posted`` to Google Jobs ``chips`` (SerpAPI). Omit when ``all``."""
    x = (date_posted or "all").strip().lower().replace("_", "").replace(" ", "").replace("-", "")
    mapping = {
        "today": "date_posted:today",
        "yesterday": "date_posted:yesterday",
        "3days": "date_posted:3days",
        "last3days": "date_posted:3days",
        "week": "date_posted:week",
        "lastweek": "date_posted:week",
        "month": "date_posted:month",
        "lastmonth": "date_posted:month",
    }
    if x in ("all", "", "anytime", "any"):
        return None
    return mapping.get(x)


def _google_search_jobs_sync(params: dict[str, Any]) -> dict[str, Any]:
    from serpapi import GoogleSearch

    search = GoogleSearch(params)
    return search.get_dict()


def _friendly_network_message(exc: BaseException) -> str | None:
    """Map DNS / TCP failures to a clear message (not confused with API quota)."""
    msg = str(exc).lower()
    if any(
        x in msg
        for x in (
            "getaddrinfo failed",
            "name resolution",
            "failed to resolve",
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
        )
    ):
        return (
            "Network/DNS: could not resolve or reach serpapi.com. "
            "Check internet, DNS (try 1.1.1.1), VPN, and firewall. "
            "SerpAPI credits were not used — the request never left your machine."
        )
    if "connection refused" in msg or "connection reset" in msg or "timed out" in msg or "timeout" in msg:
        return (
            "Network: could not complete connection to serpapi.com. "
            "Check firewall, proxy, and VPN. No API credits are charged until the server responds."
        )
    return None


def normalize_serpapi_job(raw: dict[str, Any]) -> dict[str, Any]:
    """Map SerpAPI ``jobs_results`` element to the shape expected by ``jsearch_pipeline`` helpers."""
    jid = str(raw.get("job_id") or "").strip()
    title = (raw.get("title") or "").strip()
    company = (raw.get("company_name") or "").strip()
    loc = (raw.get("location") or "").strip()
    desc = str(raw.get("description") or "").strip()
    apply_opts = raw.get("apply_options") or []
    links: list[dict[str, Any]] = []
    first_apply: str | None = None
    if isinstance(apply_opts, list):
        for o in apply_opts:
            if not isinstance(o, dict):
                continue
            link = o.get("link") or o.get("url")
            if link:
                if first_apply is None:
                    first_apply = str(link)
                links.append(
                    {
                        "title": o.get("title"),
                        "apply_link": str(link),
                    }
                )
    det = raw.get("detected_extensions") if isinstance(raw.get("detected_extensions"), dict) else {}
    work_remote = bool(det.get("work_from_home"))
    loc_l = loc.lower()
    title_l = title.lower()
    if not work_remote and (
        "remote" in loc_l
        or "work from home" in loc_l
        or loc_l in ("anywhere", "worldwide")
        or "remote" in title_l
        or "wfh" in title_l
    ):
        work_remote = True
    if not work_remote and desc:
        head = desc[:2500].lower()
        if any(
            x in head
            for x in (
                "work from home",
                "fully remote",
                "100% remote",
                "remote role",
                "remote position",
                "remote work",
                "wfh",
            )
        ):
            work_remote = True
    schedule = (det.get("schedule_type") or "").strip()
    posted = (det.get("posted_at") or "").strip()
    via = (raw.get("via") or "").strip()
    return {
        "job_id": jid,
        "job_title": title,
        "employer_name": company,
        "job_description": desc,
        "job_location": loc,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_apply_link": first_apply,
        "apply_options": links,
        "job_is_remote": work_remote,
        "job_employment_types": [schedule] if schedule else [],
        "job_posted_at": posted,
        "job_posted_at_datetime_utc": "",
        "source_board": via,
    }


async def serpapi_google_jobs_search(
    query: str,
    *,
    country_gl: str = "",
    location: str = "",
    chips: str | None = None,
    num_pages: int = 1,
    no_cache: bool = False,
    _chips_retry_done: bool = False,
) -> dict[str, Any]:
    """
    ``query`` should be a **short job title** (e.g. ``Data Scientist``), not a long keyword blob.
    ``location`` should be ``City, Country`` when possible (e.g. ``Delhi, India``).
    Returns ``{"jobs": [normalized dicts, ...]}``.
    """
    if settings.serpapi_dry_run:
        log.info("SerpAPI dry run: skipping HTTP, returning sample job")
        sample = normalize_serpapi_job(
            {
                "job_id": "dry-run-sample-1",
                "title": "Sample role (SERPAPI_DRY_RUN)",
                "company_name": "Example Corp",
                "location": "Remote",
                "description": "This is a mock listing for UI testing. Set SERPAPI_DRY_RUN=false and SERPAPI_KEY to search real jobs.",
                "apply_options": [{"title": "Example", "link": "https://example.com"}],
                "detected_extensions": {"schedule_type": "Full-time", "work_from_home": True},
                "via": "dry-run",
            }
        )
        return {"jobs": [sample]}

    key = _serpapi_key()
    if not key:
        raise ValueError(
            "SerpAPI key not configured. Set SERPAPI_KEY in backend/.env (see https://serpapi.com/dashboard)."
        )

    q = (query or "").strip()
    if not q:
        raise ValueError("Empty job search query")

    gl = to_serpapi_gl(country_gl) if country_gl else ""
    loc = (location or "").strip()
    chip = (chips or "").strip() or None
    pages = max(1, min(int(num_pages or 1), 3))

    aggregated: list[dict[str, Any]] = []
    next_token: str | None = None
    last_error: str | None = None

    for page_idx in range(pages):
        params: dict[str, Any] = {
            "engine": "google_jobs",
            "q": q,
            "api_key": key,
            "hl": "en",
        }
        if gl:
            params["gl"] = gl
        if loc:
            params["location"] = loc
        if chip:
            params["chips"] = chip
        if no_cache:
            params["no_cache"] = True
        if next_token:
            params["next_page_token"] = next_token

        data: dict[str, Any] | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                data = await asyncio.to_thread(_google_search_jobs_sync, params)
                if isinstance(data, dict):
                    break
                last_error = "SerpAPI returned non-object response"
            except Exception as e:
                last_error = _friendly_network_message(e) or str(e)
                log.warning("SerpAPI attempt %s/%s: %s", attempt + 1, MAX_ATTEMPTS, last_error)
            await asyncio.sleep(1.0 * (2**attempt))

        if not isinstance(data, dict):
            raise RuntimeError(last_error or "SerpAPI request failed")

        err = data.get("error")
        if err:
            raise RuntimeError(str(err))

        jobs_raw = data.get("jobs_results")
        if isinstance(jobs_raw, list):
            for row in jobs_raw:
                if isinstance(row, dict):
                    aggregated.append(normalize_serpapi_job(row))

        pag = data.get("serpapi_pagination")
        next_token = None
        if isinstance(pag, dict):
            nt = pag.get("next_page_token")
            if isinstance(nt, str) and nt.strip():
                next_token = nt.strip()

        if page_idx + 1 >= pages or not next_token:
            break

    if not aggregated and chip and not _chips_retry_done:
        log.info(
            "SerpAPI google_jobs returned 0 jobs with chips=%s; retrying same query without chips",
            chip,
        )
        return await serpapi_google_jobs_search(
            query,
            country_gl=country_gl,
            location=location,
            chips=None,
            num_pages=num_pages,
            no_cache=no_cache,
            _chips_retry_done=True,
        )

    return {"jobs": aggregated}
