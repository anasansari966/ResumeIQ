"""
Deterministic repair of parsed resume JSON: contact/summary from PDF glue, education/projects sections, placeholders.
Runs after LLM/heuristic so data displays correctly even when the model misses or source text was not stored.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas import ContactBlock
from app.services.resume_parser import (
    EMAIL_RE,
    PHONE_RE,
    _extract_email,
    _extract_github,
    _extract_linkedin,
    _extract_location,
    _extract_phone,
    _strip_contact_noise_from_summary,
    clean_resume_text,
    heuristic_resume_structure,
)

log = logging.getLogger(__name__)

_PHONE_LOOSE = re.compile(
    r"(?:♂|phone|tel\.?|mob\.?|mobile)\s*[:+\s\-]*(\+?\d[\d\s\-().]{8,}\d)",
    re.I,
)
_LOC_LINE = re.compile(
    r"\b([A-Z][A-Z\s]{1,42},\s*(?:INDIA|USA|UK|UAE|CANADA))\b",
)
_SUMMARY_JUNK = re.compile(
    r"(?i)(/envel[—–\-]?|♂|linkedin\s*www\.|phone\s*\+|linkedin\.com/in/[\w\-]+|"
    r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d\s\-]{9,}\d)",
)

_LINKEDIN_ANY = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/([\w\-]+)/?",
    re.I,
)


def prenormalize_raw_blob(text: str) -> str:
    """Fix common PDF extraction artifacts before regex extraction (single-line friendly)."""
    t = text.replace("\ufeff", "")
    t = re.sub(r"\(cid:\d+\)", " ", t)
    t = t.replace("linkedinwww.", "https://www.linkedin.")
    t = t.replace("linkedin www.", "https://www.linkedin.")
    t = re.sub(r"/envel[—–\-]?", " ", t, flags=re.I)
    t = re.sub(r"\benvel\w*[/—–\-]?", " ", t, flags=re.I)
    t = re.sub(r"[♂♀⚥⌢]", " ", t)
    t = re.sub(r"(?i)phone\s*\+", "+", t)
    t = re.sub(r"(?i)(\bTechnical)\s+(\bSkills\b)", r"\1 \2", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


def prenormalize_preserve_lines(text: str) -> str:
    """Like prenormalize but keep line breaks so Education / Projects sections can be sliced."""
    t = text.replace("\ufeff", "")
    t = re.sub(r"\(cid:\d+\)", " ", t)
    t = t.replace("linkedinwww.", "https://www.linkedin.")
    t = t.replace("linkedin www.", "https://www.linkedin.")
    t = re.sub(r"/envel[—–\-]?", " ", t, flags=re.I)
    t = re.sub(r"\benvel\w*[/—–\-]?", " ", t, flags=re.I)
    t = re.sub(r"[♂♀⚥⌢]", " ", t)
    t = re.sub(r"(?i)phone\s*\+", "+", t)
    t = re.sub(r"(?i)(\bTechnical)\s+(\bSkills\b)", r"\1 \2", t)
    lines: list[str] = []
    for ln in t.splitlines():
        s = re.sub(r"[ \t]+", " ", ln).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)


def salvage_blob_from_parsed(parsed: dict[str, Any]) -> str:
    parts: list[str] = []
    s = parsed.get("summary")
    if s:
        parts.append(str(s))
    for e in parsed.get("experience") or []:
        if isinstance(e, dict):
            for b in e.get("bullets") or []:
                parts.append(str(b))
    sk = parsed.get("skills") or {}
    if isinstance(sk, dict):
        for x in sk.get("technical") or []:
            parts.append(str(x))
    return "\n".join(parts)


def extract_contact_aggressive(blob: str) -> dict[str, str]:
    """Pull contact fields from messy one-line PDF dumps."""
    raw = prenormalize_raw_blob(blob)
    email = _extract_email(raw) or _extract_email(blob)
    phone = _extract_phone(raw) or _extract_phone(blob)
    if not phone:
        m = _PHONE_LOOSE.search(blob) or _PHONE_LOOSE.search(raw)
        if m:
            phone = re.sub(r"\s+", " ", m.group(1)).strip()
    linkedin = _extract_linkedin(raw) or _extract_linkedin(blob)
    if not linkedin:
        m = _LINKEDIN_ANY.search(raw) or _LINKEDIN_ANY.search(blob)
        if m:
            linkedin = f"https://www.linkedin.com/in/{m.group(1).strip('/')}"
    if linkedin and not linkedin.startswith("http"):
        linkedin = "https://" + linkedin.lstrip("/")
    github = _extract_github(raw) or _extract_github(blob)
    location = _extract_location(raw) or _extract_location(blob)
    if not location:
        m = _LOC_LINE.search(blob[:3000]) or _LOC_LINE.search(raw[:3000])
        if m:
            loc = m.group(1).strip()
            location = ", ".join(w.title() if w.isupper() and len(w) > 2 else w for w in re.split(r",\s*", loc))
    return {
        k: v
        for k, v in {"email": email, "phone": phone, "linkedin": linkedin, "github": github, "location": location}.items()
        if v
    }


def _slice_after_header(blob: str, headers: tuple[str, ...], stops: tuple[str, ...]) -> str:
    t = prenormalize_raw_blob(blob)
    hp = "|".join(headers)
    m = re.search(rf"(?is)\b({hp})\b\s*[:]?\s*", t)
    if not m:
        return ""
    rest = t[m.end() :]
    sp = "|".join(re.escape(s) for s in stops)
    m2 = re.search(rf"(?im)^\s*(?:{sp})\b", rest)
    if m2:
        return rest[: m2.start()].strip()
    return rest.strip()[:6000]


def education_keyword_fallback(blob: str) -> list[dict[str, Any]]:
    """When section headers are missing, grab lines that look like degrees or schools."""
    lines = [ln.strip() for ln in prenormalize_raw_blob(blob).splitlines() if ln.strip()]
    found: list[dict[str, Any]] = []
    year_re = re.compile(r"\b(?:19|20)\d{2}\b")
    for ln in lines:
        low = ln.lower()
        if len(ln) > 120:
            continue
        if not any(
            k in low
            for k in (
                "b.tech",
                "b.tech.",
                "b.e ",
                "bachelor",
                "m.tech",
                "master",
                "mba ",
                "ph.d",
                "phd",
                "diploma",
                "b.sc",
                "m.sc",
                "university",
                "institute of",
                "college",
            )
        ):
            continue
        yr = ""
        ym = year_re.search(ln)
        if ym:
            yr = ym.group(0)
        inst = "—"
        deg = ln
        if "university" in low or "institute" in low or "college" in low:
            inst = ln
            deg = ""
        found.append({"institution": inst, "degree": deg, "field": "", "year": yr, "gpa": None})
    return found[:6]


def scrape_education_lines(blob: str) -> list[dict[str, Any]]:
    block = _slice_after_header(
        blob,
        ("education", "academic background", "academic", "qualification"),
        (
            "technical skills",
            "skills",
            "professional experience",
            "work experience",
            "experience",
            "projects",
            "certifications",
            "certification",
        ),
    )
    if not block:
        return []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip() and len(ln.strip()) > 2]
    year_re = re.compile(r"\b(?:19|20)\d{2}\b")
    out: list[dict[str, Any]] = []
    buf: list[str] = []
    for ln in lines:
        if ln.lower() in ("education", "academic"):
            continue
        if ln[:1] in "•-*–" or re.match(r"^\d+\.", ln):
            if buf:
                out.append(_flush_edu_buf(buf, year_re))
                buf = []
            buf.append(ln.lstrip("•-*–0123456789.) "))
        elif len(buf) < 6:
            buf.append(ln)
        if len(buf) >= 8:
            out.append(_flush_edu_buf(buf, year_re))
            buf = []
    if buf:
        out.append(_flush_edu_buf(buf, year_re))
    return [x for x in out if x.get("institution") or x.get("degree")]


def _flush_edu_buf(buf: list[str], year_re: re.Pattern) -> dict[str, Any]:
    text = " ".join(buf)
    year = ""
    for ln in buf:
        ym = year_re.search(ln)
        if ym:
            year = ym.group(0)
    degree = ""
    inst = ""
    field = ""
    for ln in buf:
        low = ln.lower()
        if any(
            k in low
            for k in (
                "b.tech",
                "b.e",
                "bachelor",
                "m.tech",
                "master",
                "m.s",
                "ph.d",
                "phd",
                "diploma",
                "b.sc",
                "m.sc",
                "mba",
                "bca",
                "mca",
            )
        ):
            degree = ln
        elif "university" in low or "institute" in low or "college" in low:
            inst = ln
        elif len(ln) > 3 and not year_re.search(ln):
            field = field or ln
    if not inst and len(buf) == 1:
        inst = buf[0]
    return {
        "institution": inst or "—",
        "degree": degree or "",
        "field": field or "",
        "year": year or "",
        "gpa": None,
    }


def scrape_projects_lines(blob: str) -> list[dict[str, Any]]:
    block = _slice_after_header(
        blob,
        ("projects", "personal projects", "key projects"),
        (
            "education",
            "technical skills",
            "skills",
            "professional experience",
            "work experience",
            "experience",
            "certifications",
        ),
    )
    if not block:
        return []
    projects: list[dict[str, Any]] = []
    for line in block.splitlines():
        t = line.strip()
        if not t or len(t) < 3:
            continue
        if t[:1] in "•-*–" or re.match(r"^\d+\.", t):
            name = t.lstrip("•-*–0123456789.) ").strip()[:200]
            if name:
                projects.append({"name": name, "description": "", "tech_stack": [], "link": None})
        elif ":" in t and len(t) < 220:
            a, b = t.split(":", 1)
            projects.append({"name": a.strip()[:200], "description": b.strip()[:800], "tech_stack": [], "link": None})
    return projects[:15]


def normalize_technical_skills(items: list[Any]) -> list[str]:
    out: list[str] = []
    for x in items:
        s = str(x).strip()
        if not s:
            continue
        if re.match(r"^(languages|frameworks|tools|generative\s+ai)\s*:", s, re.I):
            _, right = s.split(":", 1)
            for p in re.split(r"[,;|]", right):
                p = p.strip()
                if p:
                    out.append(p)
            continue
        out.append(s)
    seen: set[str] = set()
    uniq = []
    for x in out:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq[:120]


def aggressive_strip_summary(summary: str, contact: ContactBlock) -> str:
    s = _strip_contact_noise_from_summary(summary, contact)
    s = prenormalize_raw_blob(s)
    s = EMAIL_RE.sub(" ", s)
    s = PHONE_RE.sub(" ", s)
    s = re.sub(r"https?://(?:www\.)?linkedin\.com/\S+", " ", s, flags=re.I)
    s = re.sub(r"linkedin\s*www\.\S+", " ", s, flags=re.I)
    s = re.sub(r"(?i)\b(delhi|mumbai|bangalore|hyderabad)\b[^.!?]*india\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+\b(Education|Skills|Technical\s+Skills|Experience)\s*$", "", s, flags=re.I)
    if len(s) < 25 or _SUMMARY_JUNK.search(s):
        # One more pass: keep only alphabetic sentences
        bits = re.split(r"(?<=[.!?])\s+", s)
        kept = [b for b in bits if b and "@" not in b and "+" not in b[:3] and "http" not in b.lower()]
        s = " ".join(kept).strip()
    if len(s) < 15 or _SUMMARY_JUNK.search(s):
        return ""
    return s[:2000]


def fix_experience_entries(parsed: dict[str, Any]) -> None:
    bad_company = re.compile(r"see\s+full|full\s+resume|\(see", re.I)
    bad_title = {"professional experience", "work experience", "experience", "employment"}
    for e in parsed.get("experience") or []:
        if not isinstance(e, dict):
            continue
        c = (e.get("company") or "").strip()
        t = (e.get("title") or "").strip()
        if bad_company.search(t):
            t = ""
        if bad_company.search(c) or c in ("(see full resume)",):
            c = ""
        if (t or "").lower() in bad_title:
            t = ""
        if (c or "").lower() in bad_title:
            c = ""
        e["company"] = (c or "—") if (c or t or (e.get("bullets") or [])) else "—"
        e["title"] = t


def _experience_is_broken(exps: list[Any]) -> bool:
    if not exps:
        return True
    bad = re.compile(r"see\s+full|full\s+resume|\(see", re.I)
    bad_c = {"professional experience", "work experience", "experience", "employment"}
    ok_roles = 0
    for e in exps:
        if not isinstance(e, dict):
            continue
        t = (e.get("title") or "").strip()
        c = (e.get("company") or "").strip()
        if bad.search(t) or bad.search(c):
            return True
        if t.lower() in bad_c or c.lower() in bad_c:
            return True
        substantive = (t and t.lower() not in bad_c) or (
            c and c not in ("—", "-") and c.lower() not in bad_c
        )
        if substantive and (e.get("bullets") or []):
            ok_roles += 1
    return ok_roles == 0


def _edu_is_empty(edu: list[Any]) -> bool:
    for ed in edu or []:
        if not isinstance(ed, dict):
            continue
        inst = str(ed.get("institution") or "").strip()
        deg = str(ed.get("degree") or "").strip()
        if (inst and inst != "—") or deg:
            return False
    return True


def _fix_pe_glued_email(email: str) -> str:
    m = re.match(r"(?i)^pe([a-z][a-z0-9.+-]{6,}@[\w.-]+\.\w+)$", (email or "").strip())
    return m.group(1) if m else email


def _merge_contact_baselines(parsed_c: dict[str, Any], heuristic_c: dict[str, Any]) -> dict[str, Any]:
    out = dict(parsed_c or {})
    h = heuristic_c or {}
    hn = str(h.get("name") or "").strip()
    pn = str(out.get("name") or "").strip()
    if (not pn or pn.lower() == "candidate") and hn and hn.lower() != "candidate":
        out["name"] = hn
        pn = out["name"]

    for k in ("email", "phone", "linkedin", "github"):
        pv = str(out.get(k) or "").strip()
        hv = str(h.get(k) or "").strip()
        if not pv and hv:
            out[k] = hv
        elif k == "linkedin" and hv and "linkedin.com" in hv.lower():
            if not pv or (hv.startswith("http") and not pv.startswith("http")):
                out[k] = hv
            elif len(hv) > len(pv) + 5:
                out[k] = hv

    pv_loc = str(out.get("location") or "").strip()
    hv_loc = str(h.get("location") or "").strip()
    if hv_loc:
        if not pv_loc or len(pv_loc) > 55 or (pn and pn.lower() in pv_loc.lower()):
            out["location"] = hv_loc
    elif not pv_loc:
        out["location"] = ""

    em = str(out.get("email") or "").strip()
    if em:
        fixed = _fix_pe_glued_email(em)
        if fixed != em:
            out["email"] = fixed
    return out


def comprehensive_salvage(parsed: dict[str, Any], cleaned_fallback: str = "") -> dict[str, Any]:
    """
    Mutates a shallow copy of parsed resume dict: contact, summary, education, projects, skills, experience.
    Preserves _resumeiq_* keys.
    """
    out = dict(parsed)
    meta = str(out.get("_resumeiq_cleaned") or "").strip()
    salvage_txt = salvage_blob_from_parsed(out)
    blob = "\n\n".join(x for x in (meta, cleaned_fallback, salvage_txt) if x.strip())

    if not blob.strip():
        log.warning("comprehensive_salvage: empty blob")
        return out

    pre = prenormalize_raw_blob(blob)
    section_source = (meta or cleaned_fallback).strip()
    section_text = clean_resume_text(section_source) if section_source else ""
    line_preserved = prenormalize_preserve_lines(section_text) if section_text else ""

    extracted = extract_contact_aggressive(pre)

    contact = dict(out.get("contact") or {})
    for key in ("email", "phone", "linkedin", "github", "location"):
        v = extracted.get(key)
        if v:
            contact[key] = v
    contact.setdefault("name", "")

    heuristic: dict[str, Any] = {}
    if len(section_text) > 80:
        try:
            heuristic = heuristic_resume_structure(section_text)
        except Exception as e:
            log.warning("heuristic_resume_structure failed: %s", e)

    if heuristic:
        contact = _merge_contact_baselines(contact, heuristic.get("contact") or {})

    cb = ContactBlock.model_validate(contact)
    out["contact"] = cb.model_dump()

    out["summary"] = aggressive_strip_summary(str(out.get("summary") or ""), cb)
    if heuristic:
        hs = aggressive_strip_summary(str(heuristic.get("summary") or ""), cb)
        if (not (out.get("summary") or "").strip() or len(str(out.get("summary") or "")) < 40) and hs:
            out["summary"] = hs
        elif _SUMMARY_JUNK.search(str(out.get("summary") or "")) and hs:
            out["summary"] = hs

    fix_experience_entries(out)

    if heuristic and _experience_is_broken(out.get("experience") or []):
        hexp = heuristic.get("experience") or []
        if hexp:
            out["experience"] = [dict(x) if isinstance(x, dict) else x for x in hexp]

    edu_existing = out.get("education") or []
    has_real_edu = not _edu_is_empty(edu_existing)

    if heuristic and _edu_is_empty(edu_existing):
        he_edu = heuristic.get("education") or []
        if he_edu:
            out["education"] = [dict(x) if isinstance(x, dict) else x for x in he_edu]
            has_real_edu = True

    if not has_real_edu:
        scraped = scrape_education_lines(line_preserved or section_text)
        if not scraped:
            scraped = education_keyword_fallback(pre)
        if scraped:
            out["education"] = scraped

    proj_existing = out.get("projects") or []
    if not proj_existing or not any(isinstance(p, dict) and (p.get("name") or "").strip() for p in proj_existing):
        scraped_p = scrape_projects_lines(line_preserved or section_text)
        if not scraped_p and heuristic:
            hp = heuristic.get("projects") or []
            if hp:
                scraped_p = [dict(x) if isinstance(x, dict) else x for x in hp]
        if scraped_p:
            out["projects"] = scraped_p

    sk = out.get("skills") or {}
    if isinstance(sk, dict):
        sk = dict(sk)
        tech = normalize_technical_skills(sk.get("technical") or [])
        if heuristic:
            ht = (heuristic.get("skills") or {}).get("technical") or []
            merged = list(dict.fromkeys(tech + [str(x) for x in ht if str(x).strip()]))[:120]
            if len(merged) > len(tech):
                tech = merged
        sk["technical"] = tech
        out["skills"] = sk

    if not (out.get("summary") or "").strip():
        bullets = []
        for e in out.get("experience") or []:
            if isinstance(e, dict):
                bullets.extend(e.get("bullets") or [])
        if bullets:
            out["summary"] = (" ".join(bullets[:2]))[:900] + ("…" if len(bullets) > 2 else "")

    return out


def strip_resume_internal_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Remove keys not meant for LLM / PDF (e.g. stored full text)."""
    return {k: v for k, v in d.items() if not str(k).startswith("_resumeiq")}
