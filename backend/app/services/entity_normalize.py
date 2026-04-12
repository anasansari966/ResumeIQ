"""Canonical brand / company spellings after PDF cleanup or LLM output."""
from __future__ import annotations

import re
from typing import Any

# Product / framework names often split by PDF extraction or naive tokenization.
_TECH_BRAND_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Lang\s*Chain", re.I), "LangChain"),
    (re.compile(r"Fast\s*API", re.I), "FastAPI"),
    (re.compile(r"Crew\s*AI", re.I), "CrewAI"),
    (re.compile(r"Open\s*CV", re.I), "OpenCV"),
    (re.compile(r"Py\s*Torch", re.I), "PyTorch"),
    (re.compile(r"Tensor\s*Flow", re.I), "TensorFlow"),
    (re.compile(r"Scikit\s*\-?\s*Learn", re.I), "Scikit-Learn"),
    (re.compile(r"Hu\s*BERT", re.I), "HuBERT"),
]

# Employer / product names (avoid splitting well-known brands).
_COMPANY_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDocu\s*Sign\b", re.I), "DocuSign"),
    (re.compile(r"\bSig\s*Tuple\b", re.I), "SigTuple"),
    (re.compile(r"\bSymphony\s*AI\b", re.I), "SymphonyAI"),
    (re.compile(r"\bTally\s*Prime\b", re.I), "Tally Prime"),
]


def normalize_tech_brands(text: str) -> str:
    if not text:
        return text
    t = text
    for pat, repl in _TECH_BRAND_SUBS:
        t = pat.sub(repl, t)
    return t


def normalize_company_brand(text: str) -> str:
    if not text:
        return text
    t = text
    for pat, repl in _COMPANY_SUBS:
        t = pat.sub(repl, t)
    return t


def normalize_resume_entities(parsed: dict[str, Any]) -> dict[str, Any]:
    """Apply brand fixes to experience, skills, projects, and summary text."""
    out = dict(parsed)

    summ = out.get("summary")
    if isinstance(summ, str) and summ:
        out["summary"] = normalize_tech_brands(summ)

    exps = out.get("experience") or []
    if isinstance(exps, list):
        for e in exps:
            if not isinstance(e, dict):
                continue
            if e.get("company"):
                e["company"] = normalize_company_brand(str(e["company"]))
            for k in ("title",):
                if e.get(k):
                    e[k] = normalize_tech_brands(str(e[k]))
            bullets = e.get("bullets") or []
            if isinstance(bullets, list):
                e["bullets"] = [normalize_tech_brands(str(b)) for b in bullets if b is not None]
            desc = e.get("description") or []
            if isinstance(desc, list):
                e["description"] = [normalize_tech_brands(str(d)) for d in desc if d is not None]

    sk = out.get("skills") or {}
    if isinstance(sk, dict):
        for key in ("technical", "soft", "tools", "certifications"):
            lst = sk.get(key) or []
            if isinstance(lst, list):
                sk[key] = [normalize_tech_brands(str(x)) for x in lst if x is not None]
        out["skills"] = sk

    projs = out.get("projects") or []
    if isinstance(projs, list):
        for p in projs:
            if not isinstance(p, dict):
                continue
            if p.get("name"):
                p["name"] = normalize_tech_brands(str(p["name"]))
            if p.get("description"):
                p["description"] = normalize_tech_brands(str(p["description"]))
            ts = p.get("tech_stack") or []
            if isinstance(ts, list):
                p["tech_stack"] = [normalize_tech_brands(str(x)) for x in ts if x is not None]

    aw = out.get("awards") or []
    if isinstance(aw, list):
        out["awards"] = [normalize_tech_brands(str(x)) for x in aw if x is not None]

    pub = out.get("publications") or []
    if isinstance(pub, list):
        out["publications"] = [normalize_tech_brands(str(x)) for x in pub if x is not None]

    return out
