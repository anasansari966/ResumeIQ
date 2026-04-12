"""Fetch job description text from a public apply URL (LinkedIn view page, ATS / career sites)."""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_LINKEDIN_HEADERS = {
    **_BROWSER_HEADERS,
    "authority": "www.linkedin.com",
}


def extract_linkedin_job_id(url: str) -> str | None:
    if not url or "linkedin.com" not in url.lower():
        return None
    m = re.search(r"/jobs/view/(?:[\w-]+/)?(\d+)(?:/|\?|#|$)", url, re.I)
    if m:
        return m.group(1)
    m = re.search(r"[?&](?:currentJobId|jobPostingId)=(\d+)", url, re.I)
    return m.group(1) if m else None


def _linkedin_markup_to_text(soup: BeautifulSoup) -> str:
    div = soup.find("div", class_=lambda x: x and "show-more-less-html__markup" in str(x))
    if div:
        return div.get_text("\n", strip=True)
    article = soup.find("article")
    if article:
        t = article.get_text("\n", strip=True)
        if len(t) > 120:
            return t
    return ""


async def fetch_linkedin_description(job_id: str, *, timeout: float = 22.0) -> str:
    view_url = f"https://www.linkedin.com/jobs/view/{job_id}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            r = await client.get(view_url, headers=_LINKEDIN_HEADERS)
    except Exception as e:
        log.warning("LinkedIn job page fetch failed: %s", e)
        return ""
    if r.status_code != 200:
        return ""
    if "signup" in str(r.url).lower() or "login" in str(r.url).lower():
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    return _linkedin_markup_to_text(soup)


def _generic_extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    og = soup.find("meta", property="og:description")
    if og and (c := (og.get("content") or "").strip()) and len(c) > 100:
        return c

    md = soup.find("meta", attrs={"name": "description"})
    if md and (c := (md.get("content") or "").strip()) and len(c) > 100:
        return c

    item = soup.find(attrs={"itemprop": "description"})
    if item:
        t = item.get_text("\n", strip=True)
        if len(t) > 200:
            return t

    for sel in (
        "#job-description",
        "#job_description",
        "[id*='job-description']",
        "[id*='job_description']",
        ".job-description",
        ".description__text",
        "#content",
        "#app_body",
    ):
        el = soup.select_one(sel)
        if el:
            t = el.get_text("\n", strip=True)
            if len(t) > 250:
                return t

    main = soup.find("main")
    if main:
        t = main.get_text("\n", strip=True)
        if len(t) > 400:
            return t

    article = soup.find("article")
    if article:
        t = article.get_text("\n", strip=True)
        if len(t) > 400:
            return t

    body = soup.find("body")
    if body:
        t = body.get_text("\n", strip=True)
        if len(t) > 500:
            return t[:50_000]
    return ""


async def fetch_generic_career_page(url: str, *, timeout: float = 22.0) -> str:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ""
    except Exception:
        return ""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            r = await client.get(url, headers=_BROWSER_HEADERS)
    except Exception as e:
        log.warning("Career page fetch failed for %s: %s", url[:80], e)
        return ""
    if r.status_code != 200:
        return ""
    return _generic_extract_text(r.text)


async def fetch_description_from_apply_url(apply_url: str) -> str:
    """
    Best-effort description: LinkedIn job view HTML, otherwise generic ATS / career page parsing.
    """
    u = (apply_url or "").strip()
    if not u:
        return ""
    li_id = extract_linkedin_job_id(u)
    if li_id:
        text = await fetch_linkedin_description(li_id)
        if text.strip():
            return text.strip()
    return (await fetch_generic_career_page(u)).strip()
