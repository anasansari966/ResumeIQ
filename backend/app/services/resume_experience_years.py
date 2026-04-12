"""Estimate total professional experience (years) from structured resume + summary text."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_PRESENT = re.compile(r"\b(present|current|now|today)\b", re.I)
_SUMMARY_YEARS = re.compile(
    r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience)?",
    re.I,
)


def _years_in_string(s: str) -> list[int]:
    return sorted({int(m.group(0)) for m in _YEAR.finditer(s or "")})


def _bounds_from_dates(start_s: str, end_s: str) -> tuple[int | None, int | None]:
    now_y = datetime.utcnow().year
    sy = _years_in_string(start_s or "")
    ey = _years_in_string(end_s or "")
    start = min(sy) if sy else None
    end = max(ey) if ey else None
    el = (end_s or "").strip().lower()
    if _PRESENT.search(el) or not (end_s or "").strip():
        end = now_y
    elif end is None and start is not None:
        end = now_y
    return start, end


def _merge_year_spans(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted([(a, b) for a, b in intervals if a is not None and b is not None and a <= b])
    out: list[list[int]] = []
    for a, b in intervals:
        if not out or a > out[-1][1] + 1:
            out.append([a, b])
        else:
            out[-1][1] = max(out[-1][1], b)
    return [(x[0], x[1]) for x in out]


def _years_from_experience_block(resume_json: dict[str, Any]) -> int | None:
    raw: list[tuple[int, int]] = []
    for e in resume_json.get("experience") or []:
        if not isinstance(e, dict):
            continue
        a, b = _bounds_from_dates(str(e.get("start_date") or ""), str(e.get("end_date") or ""))
        if a is None:
            continue
        if b is None:
            b = datetime.utcnow().year
        if b < a:
            b = a
        raw.append((a, b))
    merged = _merge_year_spans(raw)
    if not merged:
        return None
    total = 0
    for a, b in merged:
        total += max(1, b - a + 1)
    return max(1, min(40, total))


def _years_from_summary_text(text: str) -> int | None:
    if not text:
        return None
    m = _SUMMARY_YEARS.search(text)
    if not m:
        return None
    try:
        y = float(m.group(1))
        return max(0, min(40, int(round(y))))
    except ValueError:
        return None


def infer_total_experience_years(resume_json: dict[str, Any] | None) -> int | None:
    """
    Prefer explicit 'N years' in summary; else merged timeline from experience start/end dates.
    Returns None if nothing usable.
    """
    if not resume_json:
        return None
    summary = str(resume_json.get("summary") or "")
    from_summary = _years_from_summary_text(summary)
    if from_summary is not None and from_summary > 0:
        return from_summary
    return _years_from_experience_block(resume_json)


def experience_search_phrase(years: int | None) -> str:
    """
    Short fragment to append to JSearch query strings so boards return level-appropriate roles.
    """
    if years is None or years < 0:
        return ""
    if years <= 1:
        return "entry level 0-2 years experience"
    if years == 2:
        return "2 years experience"
    if years <= 4:
        return f"{years} years experience"
    if years <= 7:
        return f"{years} years experience mid level"
    return f"{years} years experience senior"
