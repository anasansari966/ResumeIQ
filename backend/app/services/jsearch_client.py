"""JSearch (RapidAPI) — real-time job listings with retries and safe JSON handling."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_URL = f"https://{JSEARCH_HOST}/search"
MAX_ATTEMPTS = 3


def _rapidapi_key() -> str:
    k = (settings.rapidapi_key or "").strip()
    if k:
        return k
    return (os.environ.get("RAPIDAPI_KEY") or os.environ.get("rapidapi_key") or "").strip()


async def jsearch_search(
    query: str,
    *,
    page: int = 1,
    num_pages: int = 1,
    country: str = "",
    date_posted: str = "all",
) -> dict[str, Any]:
    key = _rapidapi_key()
    if not key:
        raise ValueError("RapidAPI key not configured (set RAPIDAPI_KEY in backend/.env or export it)")
    params = {
        "query": query.strip(),
        "page": max(1, page),
        "num_pages": max(1, min(20, num_pages)),
        "date_posted": date_posted or "all",
    }
    country_value = (country or "").strip().lower()
    if country_value:
        params["country"] = country_value
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-rapidapi-key": key,
        "x-rapidapi-host": JSEARCH_HOST,
    }
    last_error: str | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=65.0) as client:
                r = await client.get(JSEARCH_URL, params=params, headers=headers)
                if r.status_code in (429, 502, 503, 504):
                    last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                    log.warning("JSearch retry %s/%s: %s", attempt + 1, MAX_ATTEMPTS, last_error)
                    await asyncio.sleep(1.2 * (2**attempt))
                    continue
                if r.status_code >= 400:
                    last_error = f"HTTP {r.status_code}: {r.text[:400]}"
                    log.warning("JSearch error: %s", last_error)
                r.raise_for_status()
                try:
                    data = r.json()
                except json.JSONDecodeError as e:
                    last_error = f"Invalid JSON: {e}"
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                if not isinstance(data, dict):
                    last_error = "Response is not a JSON object"
                    continue
                return data
        except httpx.TimeoutException as e:
            last_error = f"Timeout: {e}"
            log.warning("JSearch timeout attempt %s", attempt + 1)
            await asyncio.sleep(1.0 * (2**attempt))
        except httpx.RequestError as e:
            last_error = f"Network error: {e}"
            log.warning("JSearch request error: %s", e)
            await asyncio.sleep(1.0 * (2**attempt))
    raise RuntimeError(last_error or "JSearch request failed after retries")
