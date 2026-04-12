"""Score listings against resume + optional target JD (preference for relevance)."""
from __future__ import annotations

import re
from typing import Any

from app.services.job_seeds import match_score_resume

_STOP = frozenset(
    "the a an and or for to of in on at with from by as is are was be been being will shall "
    "this that these those we you our your they their them it its if then else not no yes "
    "all any some such more most other into out over under year years experience skills "
    "ability able strong team work working time full part remote hybrid onsite office "
    "requirements required preferred plus including include responsibilities description"
    .split()
)

_TECH = re.compile(
    r"\b(Python|JavaScript|TypeScript|React|Node\.js|Node\.?js|AWS|AWS\s*\)|Docker|Kubernetes|SQL|PostgreSQL|"
    r"MongoDB|MySQL|Java|Spring|Spring\s*Boot|C\+\+|C#|\.NET|Go|Golang|Rust|Ruby|Rails|PHP|Laravel|Swift|Kotlin|"
    r"Angular|Vue|FastAPI|Django|Flask|TensorFlow|PyTorch|MLOps|GCP|Azure|CI/CD|Git|GraphQL|REST|Redis|Kafka|"
    r"Elasticsearch|Scala|Spark|Hadoop|Snowflake|Databricks|Linux|Unix|Agile|Scrum|Jira|DevOps|"
    r"Terraform|Ansible|Jenkins|HTML|CSS|SASS|Webpack|Next\.js|Express|Microservices|API|Machine\s+Learning|"
    r"Data\s+Science|Analytics|Tableau|Power\s+BI|Excel|Salesforce|SAP)\b",
    re.I,
)


def extract_jd_keywords(jd_text: str, max_terms: int = 28) -> list[str]:
    if not jd_text or not jd_text.strip():
        return []
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}", jd_text.lower())
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in _STOP or len(w) < 3:
            continue
        if w not in seen:
            seen.add(w)
            out.append(w)
        if len(out) >= max_terms:
            break
    return out


def skills_from_jsearch_item(item: dict[str, Any]) -> list[str]:
    desc = str(item.get("job_description") or "")
    title = str(item.get("job_title") or "")
    found = [m.group(0) for m in _TECH.finditer(desc + " " + title)]
    uniq: list[str] = []
    seen: set[str] = set()
    for s in found:
        if s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    if len(uniq) < 6:
        for w in re.findall(r"\b[A-Z][a-z]+(?:\.js)?\b", title + " " + desc[:400]):
            if len(w) > 2 and w.lower() not in seen:
                seen.add(w.lower())
                uniq.append(w)
        if len(uniq) > 24:
            return uniq[:24]
    return uniq[:24] if uniq else ["General"]


def jd_alignment_score(job_description: str, job_title: str, jd_keywords: list[str]) -> float:
    if not jd_keywords:
        return 55.0
    text = f"{job_title} {job_description}".lower()
    hits = 0
    for k in jd_keywords:
        if len(k) > 2 and k.lower() in text:
            hits += 1
    return round(100.0 * hits / max(1, len(jd_keywords)), 1)


def combined_preference_score(
    job_skills: list[str],
    job_description: str,
    job_title: str,
    resume_json: dict[str, Any],
    jd_text: str | None,
) -> tuple[float, list[str], list[str]]:
    base, matching, missing = match_score_resume(job_skills, resume_json)
    if jd_text and jd_text.strip():
        jd_kw = extract_jd_keywords(jd_text)
        jd_part = jd_alignment_score(job_description, job_title, jd_kw)
        # Emphasize JD fit when user provided a target JD.
        combined = round(0.38 * base + 0.62 * jd_part, 1)
        return min(100.0, combined), matching, missing
    return base, matching, missing
