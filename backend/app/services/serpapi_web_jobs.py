"""
SerpAPI Google **organic** search to surface company career / ATS pages with direct apply links.

Uses the same SERPAPI_KEY as Google Jobs. Each organic search consumes SerpAPI credits.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.services.jsearch_pipeline import ISO2_QUERY_LABEL
from app.services.serpapi_jobs_client import _friendly_network_message, _serpapi_key, to_serpapi_gl

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

# Prefer ATS and /careers/ URLs; exclude big job boards we already scrape elsewhere.
_BLOCKED_IN_URL = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "simplyhired.com",
    "google.com/search",
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
)

_ATS_HOST_FRAGMENTS = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "jobvite.com",
    "icims.com",
    "taleo.net",
    "bamboohr.com",
    "applytojob.com",
    "workable.com",
    "teamtailor.com",
    "pinpoint.com",
    "oraclecloud.com",
    "ultipro.com",
    "hrmdirect.com",
)


def _is_career_apply_url(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u.startswith("http"):
        return False
    if any(b in u for b in _BLOCKED_IN_URL):
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    if any(h in host for h in _ATS_HOST_FRAGMENTS):
        return True
    if host.startswith("careers.") or ".careers." in host:
        return True
    path = urlparse(url).path.lower()
    if any(
        x in path
        for x in (
            "/careers",
            "/jobs/",
            "/job/",
            "/job-opportunities",
            "/openings",
            "/positions",
            "/apply",
            "jobdetails",
        )
    ):
        return True
    return False


def _split_title_company(organic_title: str, url: str) -> tuple[str, str]:
    t = (organic_title or "").strip()
    for sep in (" | ", " · ", " - ", " — "):
        if sep in t:
            left, right = t.split(sep, 1)
            left, right = left.strip(), right.strip()
            if 8 < len(left) < 180 and 2 < len(right) < 120:
                return left[:500], right[:300]
    try:
        host = urlparse(url).netloc.lower()
        parts = [p for p in host.split(".") if p not in ("www", "jobs", "boards", "careers") and len(p) > 2]
        brand = parts[-2] if len(parts) >= 2 else (parts[0] if parts else "Company")
        company = brand.replace("-", " ").title()
    except Exception:
        company = "Company"
    return (t[:500] or "Open role"), company[:300]


def _google_organic_sync(params: dict[str, Any]) -> dict[str, Any]:
    from serpapi import GoogleSearch

    return GoogleSearch(params).get_dict()


def _organic_to_item(title: str, link: str, snippet: str) -> dict[str, Any]:
    link = (link or "").strip()
    h = hashlib.sha256(link.encode("utf-8")).hexdigest()[:40]
    job_title, company = _split_title_company(title, link)
    desc = (snippet or "").strip()
    return {
        "job_id": f"web-{h}",
        "job_title": job_title,
        "employer_name": company,
        "job_description": desc,
        "job_location": "",
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_apply_link": link,
        "apply_options": [{"apply_link": link}],
        "job_is_remote": "remote" in desc.lower() or "remote" in title.lower(),
        "job_employment_types": [],
        "job_posted_at": "",
        "job_posted_at_datetime_utc": "",
    }


async def _one_organic_query(q: str, *, gl: str, max_results: int) -> list[dict[str, Any]]:
    key = _serpapi_key()
    if not key:
        return []
    params: dict[str, Any] = {
        "engine": "google",
        "q": q,
        "api_key": key,
        "hl": "en",
        "num": min(20, max(5, max_results + 5)),
    }
    if gl:
        params["gl"] = gl

    data: dict[str, Any] | None = None
    last_error = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            data = await asyncio.to_thread(_google_organic_sync, params)
            if isinstance(data, dict):
                break
            last_error = "SerpAPI returned non-object response"
        except Exception as e:
            last_error = _friendly_network_message(e) or str(e)
            log.warning("SerpAPI organic attempt %s/%s: %s", attempt + 1, MAX_ATTEMPTS, last_error)
        await asyncio.sleep(0.4 * (2**attempt))

    if not isinstance(data, dict):
        log.warning("SerpAPI organic failed: %s", last_error)
        return []

    err = data.get("error")
    if err:
        log.warning("SerpAPI organic API error: %s", err)
        return []

    organic = data.get("organic_results")
    if not isinstance(organic, list):
        return []

    out: list[dict[str, Any]] = []
    for row in organic:
        if not isinstance(row, dict):
            continue
        link = str(row.get("link") or "").strip()
        if not link or not _is_career_apply_url(link):
            continue
        title = str(row.get("title") or "Job posting").strip()
        snippet = str(row.get("snippet") or "").strip()
        out.append(_organic_to_item(title, link, snippet))
        if len(out) >= max_results:
            break
    return out


async def fetch_career_hits_from_web_search(
    role_titles: list[str],
    *,
    location_label: str,
    qcountry: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Run Google organic searches aimed at ATS / career-site apply URLs.
    Returns (normalized items like JobSpy, UI query labels).
    """
    if settings.serpapi_dry_run or not getattr(settings, "serpapi_web_jobs_enabled", True):
        return [], []
    if not _serpapi_key():
        return [], []

    max_roles = int(getattr(settings, "serpapi_web_jobs_max_roles", 2) or 0)
    max_hits = int(getattr(settings, "serpapi_web_jobs_max_hits", 10) or 10)
    if max_roles <= 0:
        return [], []

    roles = [str(r).strip() for r in role_titles if str(r).strip()][:max_roles]
    if not roles:
        return [], []

    loc = (location_label or "").strip() or "Worldwide"
    gl = to_serpapi_gl(qcountry) if (qcountry or "").strip() else ""

    labels: list[str] = []
    seen_links: set[str] = set()
    aggregated: list[dict[str, Any]] = []

    async def _run_role(role: str) -> None:
        # High-intent query: major ATS domains + location context.
        q = (
            f'{role} jobs apply (site:boards.greenhouse.io OR site:jobs.lever.co OR site:myworkdayjobs.com '
            f'OR site:jobs.smartrecruiters.com OR site:jobs.ashbyhq.com) {loc}'
        )
        labels.append(f"Web search (career sites) · {role} · {loc}")
        rows = await _one_organic_query(q, gl=gl, max_results=max_hits)
        for it in rows:
            u = str(it.get("job_apply_link") or "").strip()
            if u and u not in seen_links:
                seen_links.add(u)
                if qcountry:
                    cn = ISO2_QUERY_LABEL.get((qcountry or "")[:2].lower(), "")
                    if cn:
                        it["job_location"] = loc if loc != "Worldwide" else cn
                        it["job_country"] = cn
                aggregated.append(it)

    for role in roles:
        await _run_role(role)
        if len(aggregated) >= max_hits:
            break

    # Fallback: broader query if ATS-only returned nothing.
    if not aggregated and roles:
        role0 = roles[0]
        q2 = f"{role0} careers hiring apply {loc}"
        labels.append(f"Web search (broader) · {role0} · {loc}")
        rows = await _one_organic_query(q2, gl=gl, max_results=max_hits)
        for it in rows:
            u = str(it.get("job_apply_link") or "").strip()
            if u and u not in seen_links:
                seen_links.add(u)
                if qcountry:
                    cn = ISO2_QUERY_LABEL.get((qcountry or "")[:2].lower(), "")
                    if cn:
                        it["job_location"] = loc if loc != "Worldwide" else cn
                        it["job_country"] = cn
                aggregated.append(it)
            if len(aggregated) >= max_hits:
                break

    return aggregated[:max_hits], labels
