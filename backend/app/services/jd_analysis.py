import re
from collections import Counter
from typing import Any

_TECH = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "sql",
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "docker",
    "fastapi",
    "django",
    "flask",
    "ml",
    "ai",
    "llm",
    "data",
    "excel",
    "tableau",
    "power bi",
    "c++",
    "go",
    "rust",
    "ruby",
    "php",
    "scala",
    "spark",
    "kafka",
    "mongodb",
    "postgres",
    "redis",
    "terraform",
    "linux",
    "git",
    "agile",
    "scrum",
}


def extract_keywords_jd(text: str, top_n: int = 40) -> list[str]:
    words = re.findall(r"[A-Za-z+#][A-Za-z0-9+#./-]{1,}", text.lower())
    stop = {"the", "and", "for", "with", "you", "our", "are", "will", "this", "that", "from", "have", "years", "year", "work", "team", "role", "job", "all", "any", "per", "not"}
    filtered = [w for w in words if w not in stop and len(w) > 2]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(top_n)]


def experience_level_hints(text: str) -> dict[str, Any]:
    t = text.lower()
    yoe = None
    m = re.search(r"(\d+)\s*\+\s*years", t)
    if m:
        yoe = int(m.group(1))
    seniority = "mid"
    if any(x in t for x in ("senior", "lead", "principal", "staff", "architect")):
        seniority = "senior"
    elif any(x in t for x in ("junior", "entry", "graduate", "intern")):
        seniority = "junior"
    tone = "corporate"
    if any(x in t for x in ("startup", "fast-paced", "wear many hats")):
        tone = "startup"
    elif any(x in t for x in ("enterprise", "regulated", "compliance")):
        tone = "corporate"
    return {"yoe_hint": yoe, "seniority": seniority, "tone": tone}


def map_skills(keywords: list[str]) -> list[str]:
    found = []
    blob = " ".join(keywords)
    for tech in sorted(_TECH, key=len, reverse=True):
        if tech.replace(" ", "") in blob.replace(" ", "") or tech in blob:
            found.append(tech)
    return list(dict.fromkeys(found))[:25]


def analyze_jd(raw: str) -> dict[str, Any]:
    keywords = extract_keywords_jd(raw)
    must_have = keywords[:15]
    nice = keywords[15:30]
    level = experience_level_hints(raw)
    skills = map_skills(keywords)
    gaps_placeholder: list[str] = []
    return {
        "keywords": keywords,
        "must_have_keywords": must_have,
        "nice_to_have": nice,
        "skills_mapped": skills,
        "experience_level": level,
        "ats_priority_terms": must_have[:10],
        "summary": raw[:400].replace("\n", " "),
    }
