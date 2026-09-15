"""Deterministic job eligibility analysis using resume skills and experience."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.job_seeds import match_score_resume
from app.services.resume_experience_years import infer_total_experience_years

_YEAR_PATTERNS = (
    re.compile(r"\b(?:minimum|min\.?|at least)\s*(\d{1,2})\+?\s*(?:years?|yrs?)", re.I),
    re.compile(r"\b(\d{1,2})\+\s*(?:years?|yrs?)", re.I),
    re.compile(r"\b(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*(?:years?|yrs?)", re.I),
    re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?)\s+(?:of\s+)?experience", re.I),
)
_TOKEN = re.compile(r"[a-z][a-z0-9+#.]{1,}", re.I)
_ROLE_STOP = frozenset(
    "and or the a an for of in with remote hybrid onsite on site full time part contract role jobs job"
    " developer engineer specialist professional associate consultant".split()
)


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    score: float
    matching_skills: list[str]
    missing_skills: list[str]
    rationale: str
    reasons: list[str]
    candidate_years: int | None
    required_years: int | None


def _required_experience_years(title: str, description: str) -> int | None:
    text = f"{title} {description}"[:30_000]
    values: list[int] = []
    for pattern in _YEAR_PATTERNS:
        for match in pattern.finditer(text):
            try:
                values.append(int(match.group(1)))
            except (TypeError, ValueError):
                continue
    if values:
        return max(0, min(30, min(values)))

    low = text.lower()
    if any(term in low for term in ("internship", "intern role", "new grad", "graduate trainee", "fresher")):
        return 0
    if any(term in low for term in ("principal", "director", "head of ", "vice president", "vp ")):
        return 7
    if any(term in low for term in ("staff ", "lead ", "manager ")):
        return 5
    if "senior" in low or " sr " in f" {low} ":
        return 3
    return None


def _normalise_role_text(text: str) -> str:
    low = f" {text.lower()} "
    replacements = {
        " ai ": " artificial intelligence ",
        " ml ": " machine learning ",
        " nlp ": " natural language processing ",
        " devops ": " cloud infrastructure ",
        " qa ": " quality assurance ",
        " bi ": " business intelligence ",
    }
    for old, new in replacements.items():
        low = low.replace(old, new)
    return low


def _role_score(job_title: str, resume_json: dict[str, Any]) -> float:
    candidate_parts: list[str] = [str(resume_json.get("summary") or "")]
    for row in resume_json.get("experience") or []:
        if isinstance(row, dict):
            candidate_parts.extend((str(row.get("title") or ""), " ".join(str(x) for x in row.get("bullets") or [])))
    skills = resume_json.get("skills") or {}
    if isinstance(skills, dict):
        for key in ("technical", "tools", "soft", "certifications"):
            candidate_parts.extend(str(x) for x in skills.get(key) or [])

    title_tokens = {
        token
        for token in _TOKEN.findall(_normalise_role_text(job_title))
        if token not in _ROLE_STOP and len(token) > 2
    }
    if not title_tokens:
        return 55.0
    candidate_blob = _normalise_role_text(" ".join(candidate_parts))
    hits = sum(1 for token in title_tokens if re.search(rf"\b{re.escape(token)}\b", candidate_blob))
    return round(100 * hits / len(title_tokens), 1)


def analyze_job_eligibility(
    *,
    title: str,
    description: str,
    job_skills: list[str],
    resume_json: dict[str, Any],
    minimum_score: float = 52.0,
) -> EligibilityResult:
    """Score and gate a job using skills, generated-role alignment, and experience."""
    skill_score, matching, missing = match_score_resume(job_skills, resume_json)
    role_score = _role_score(title, resume_json)
    candidate_years = infer_total_experience_years(resume_json)
    required_years = _required_experience_years(title, description)

    if required_years is None:
        experience_score = 82.0 if candidate_years is not None else 65.0
        experience_hard_fail = False
    elif candidate_years is None:
        experience_score = 45.0 if required_years <= 1 else 10.0
        experience_hard_fail = required_years >= 2
    elif candidate_years >= required_years:
        experience_score = 100.0
        experience_hard_fail = False
    else:
        shortfall = required_years - candidate_years
        experience_score = 62.0 if shortfall == 1 else 15.0
        experience_hard_fail = shortfall >= 2

    # Education is intentionally excluded. Eligibility uses only the resume's
    # skills, experience/seniority, and generated-role alignment.
    score = round(0.50 * skill_score + 0.30 * experience_score + 0.20 * role_score, 1)
    domain_hard_fail = role_score < 20 and skill_score < 38
    eligible = score >= minimum_score and not experience_hard_fail and not domain_hard_fail

    reasons: list[str] = []
    if required_years is not None:
        if candidate_years is None:
            reasons.append(f"Requires about {required_years}+ years; resume experience could not be confirmed")
        elif candidate_years >= required_years:
            reasons.append(f"{candidate_years} years of experience meets the {required_years}+ year requirement")
        else:
            reasons.append(f"{candidate_years} years of experience is below the {required_years}+ year requirement")
    elif candidate_years is not None:
        reasons.append(f"Seniority is reasonable for approximately {candidate_years} years of experience")

    if matching:
        reasons.append(f"Matches {len(matching)} listed skill{'s' if len(matching) != 1 else ''}: {', '.join(matching[:4])}")
    elif job_skills and job_skills != ["General"]:
        reasons.append("No clearly matching required skills were found")

    if role_score >= 50:
        reasons.append("Role aligns with the candidate's prior work and profile")
    elif domain_hard_fail:
        reasons.append("Role domain does not align with the resume")

    prefix = "Eligible" if eligible else "Not eligible"
    rationale = f"{prefix}: " + ("; ".join(reasons[:3]) or "profile fit was evaluated from the available job details") + "."
    return EligibilityResult(
        eligible=eligible,
        score=score,
        matching_skills=matching,
        missing_skills=missing,
        rationale=rationale,
        reasons=reasons,
        candidate_years=candidate_years,
        required_years=required_years,
    )
