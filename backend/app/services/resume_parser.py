import io
import json
import re
from typing import Any

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.config import settings
from app.schemas import (
    ContactBlock,
    EducationItem,
    ExperienceItem,
    ProjectItem,
    ResumeSchema,
    SkillsBlock,
)

_SECTION_PATTERNS = [
    (re.compile(r"^\s*(summary|professional\s+summary|objective|profile|about)\s*:?\s*$", re.I), "summary"),
    (re.compile(r"^\s*(experience|work\s+experience|professional\s+experience|employment|career)\s*:?\s*$", re.I), "experience"),
    (re.compile(r"^\s*(education|academic|academics|qualification)\s*:?\s*$", re.I), "education"),
    (re.compile(r"^\s*(skills|technical\s+skills|core\s+competencies|key\s+skills)\s*:?\s*$", re.I), "skills"),
    (re.compile(r"^\s*(projects|personal\s+projects|key\s+projects)\s*:?\s*$", re.I), "projects"),
    (re.compile(r"^\s*(certifications?|licenses?)\s*:?\s*$", re.I), "certifications"),
]

LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?", re.I)
_MONTH_SHORT = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)
_DATE_SPAN = re.compile(
    rf"(({_MONTH_SHORT}\s+\d{{4}})\s*[–—\u2013\u2014\-\ufffd]\s*({_MONTH_SHORT}\s+\d{{4}}))\s*$",
    re.I,
)
_COMPANY_AND_DATES = re.compile(
    rf"^(.+?)\s+({_MONTH_SHORT}\s+\d{{4}})\s*[–—\u2013\u2014\-\ufffd]\s*({_MONTH_SHORT}\s+\d{{4}})\s*$",
    re.I,
)
_YEAR_ONLY_SPAN = re.compile(
    rf"^(.+?)\s+((?:19|20)\d{{2}})\s*[–—\u2013\u2014\-\ufffd]+\s*((?:19|20)\d{{2}})\s*$",
    re.I,
)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[-\s]?)?(?:\(?\d{3,5}\)?[-\s]?)?\d[\d\s().-]{6,}\d")


def _extract_email(text: str) -> str:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else ""


def _phone_match_is_grade_noise(text: str, start: int, end: int) -> bool:
    """Reject '100 2020' style fragments next to 'Percentage: 91.4/100'."""
    window = text[max(0, start - 90) : end + 12]
    if re.search(r"\d+\.\d+\s*/\s*100", window, re.I):
        return True
    raw = text[start:end].strip()
    return bool(re.match(r"^\d{2,3}\s+20(1|2)\d$", raw))


def _phone_value_suspicious(phone: str) -> bool:
    if not (phone or "").strip():
        return True
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10:
        return True
    if re.match(r"^\d{2,3}\s+20(1|2)\d$", phone.strip()):
        return True
    return False


def _extract_phone(text: str) -> str:
    """Prefer real mobiles (e.g. +91 …) over the first fuzzy match (often grade lines like 100 2020)."""
    best, best_score = "", -1
    for m in PHONE_RE.finditer(text):
        if _phone_match_is_grade_noise(text, m.start(), m.end()):
            continue
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        digits = re.sub(r"\D", "", s)
        if len(digits) < 10:
            continue
        score = len(digits)
        if "+" in s:
            score += 50
        if "91" in digits[:4]:
            score += 20
        if score > best_score:
            best_score = score
            best = s
    return best


_BAD_LLM_CONTACT_NAMES = frozenset(
    {
        "internship",
        "experience",
        "education",
        "skills",
        "projects",
        "summary",
        "candidate",
        "resume",
        "cv",
        "employment",
        "work experience",
        "professional experience",
    }
)


def _infer_name_near_contact(text: str) -> str:
    """ALL CAPS name line above ``Contact:`` / email (common on IIT-style PDFs)."""
    low = text.lower()
    idx = low.find("contact:")
    if idx < 0:
        idx = low.find("email -id:")
    if idx < 0:
        idx = low.find("linkedin:")
    blob = text[max(0, idx - 1600) : idx] if idx >= 0 else text[-2200:]
    lines = [ln.strip() for ln in blob.replace("\r", "").split("\n") if ln.strip()]
    for ln in reversed(lines[-60:]):
        if len(ln) < 3 or len(ln) > 70:
            continue
        letters = ln.replace(" ", "")
        if not letters.isalpha():
            continue
        if not ln.isupper():
            continue
        up = ln.upper()
        if any(
            x in up
            for x in (
                "INSTITUTE",
                "TECHNOLOGY",
                "UNIVERSITY",
                "SCHOOL",
                "COLLEGE",
                "DEPARTMENT",
            )
        ):
            continue
        return ln.strip().title()
    return ""


def _extract_linkedin(text: str) -> str:
    fix = text.replace("linkedinwww.", "linkedin www.").replace("linkedinwww", "linkedin www.")
    m = LINKEDIN_RE.search(fix)
    return (m.group(0).rstrip("/") if m else "")


def _extract_github(text: str) -> str:
    m = GITHUB_RE.search(text)
    return m.group(0).rstrip("/") if m else ""


def _extract_location(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:10]:
        if EMAIL_RE.search(ln) or "@" in ln:
            continue
        if re.search(r",\s*(India|USA|UK|UAE|Canada|Germany|Remote)\b", ln, re.I) and len(ln) < 80:
            if not ln.lower().startswith("http"):
                return re.sub(r"\s+", " ", ln)
    m = re.search(
        r"\b([A-Z][A-Z\s]{2,40},\s*(?:INDIA|USA|UK|UAE|CANADA)|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*(?:India|USA|UK|UAE))\b",
        text[:2000],
    )
    if m:
        return m.group(1).strip()
    return ""


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def parse_pdf(data: bytes) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            parts = [(p.extract_text() or "") for p in pdf.pages]
        joined = "\n".join(parts)
        if joined.strip():
            return joined
    except Exception:
        pass
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def parse_docx(data: bytes) -> str:
    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _insert_newlines_before_headers(text: str) -> str:
    """Turn glued headers like '... gmail.com Education' into separate lines."""
    t = text
    t = re.sub(
        r"(?<=[\w.@+)])(?=\s*(?:Education|Technical Skills|Skills|Projects|Certifications|Experience|Work Experience)\b)",
        "\n",
        t,
        flags=re.I,
    )
    return t


def normalize_pdf_extraction_artifacts(raw: str) -> str:
    """
    Repair common PDF-to-text glue: icon glyphs, "/envel…" junk before emails,
    spurious ``pe`` before the email local-part, and ``linkedinwww`` without a scheme.
    """
    t = raw.replace("\ufeff", "")
    t = re.sub(r"\(cid:\d+\)", " ", t)
    # linkedinwww.linkedin… -> https://www.linkedin… (optional slashes/spaces before)
    t = re.sub(r"[/\s,;·|]*linkedin\s*www\.", " https://www.", t, flags=re.I)
    # Drop "/envel…" up to (but not including) a real email — handles ⌢ and partial "envel" tokens
    t = re.sub(r"/envel[^@]*?(?=[a-z0-9._%+-]+@)", " ", t, flags=re.I)
    t = re.sub(r"/envel[—–\-]?", " ", t, flags=re.I)
    t = re.sub(r"/envel\w*\b", " ", t, flags=re.I)
    t = re.sub(r"\benvel\w*[—–\-]?", " ", t, flags=re.I)
    t = re.sub(r"\benvel\w*\b", " ", t, flags=re.I)
    # Phone / envelope / bullet icons rendered as Unicode
    t = re.sub(r"[♂♀⚥⌢⌣✉✔✓□▪▸►·●◆◇■]", " ", t)
    # Envelope icon + stray "p" glued to email (keep address: strip leading "pe" glue only when plausible)
    t = re.sub(
        r"(?i)\bpe([a-z][a-z0-9._%+-]{5,}@[a-z0-9.-]+\.[a-z]{2,})\b",
        r"\1",
        t,
    )
    # "phone" label and symbol runs before +<number>
    t = re.sub(r"(?i)[♂♀⚥]{0,3}\s*phone\s*", " ", t)
    t = re.sub(r"(?i)\bphone\s*\+", "+", t)
    # Readable separator between phone and email when glued on one line
    t = re.sub(r"(\+\d[\d\s().-]{8,}\d)\s+(?=[a-z0-9._%+-]+@)", r"\1 · ", t, flags=re.I)
    t = re.sub(r"\s#\s", " ", t)
    t = re.sub(r"(\d{4})\s*\ufffd\s*(\d{4})", r"\1 – \2", t)
    t = t.replace("\ufffd", " – ")
    return t


def clean_resume_text(raw: str) -> str:
    t = normalize_pdf_extraction_artifacts(raw)
    t = re.sub(r"(?i)(\bTechnical)\s*\n\s*(\bSkills\b)", r"\1 \2", t)
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = _insert_newlines_before_headers(t)
    return t.strip()


def _classify_line_header(line: str) -> str | None:
    ln = line.strip()
    for pat, key in _SECTION_PATTERNS:
        if pat.match(ln):
            return key
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    keys = ("summary", "experience", "education", "skills", "projects", "certifications", "other")
    sections: dict[str, list[str]] = {k: [] for k in keys}
    current = "other"
    for ln in lines:
        hdr = _classify_line_header(ln)
        if hdr:
            current = hdr
            continue
        sections[current].append(ln)
    return sections


def _infer_name(lines: list[str]) -> str:
    skip = {"resume", "cv", "curriculum vitae", "education", "experience", "skills"}
    caps_name = re.compile(r"^[A-Z][A-Z\s.]{3,54}$")
    title_name = re.compile(r"^([A-Z][a-z]+\s+){1,4}[A-Z][a-z]+$")
    for ln in lines[:14]:
        low = ln.lower().strip()
        if EMAIL_RE.search(ln) or LINKEDIN_RE.search(ln) or PHONE_RE.search(ln):
            continue
        if len(ln) > 70 or ln.count(" ") > 8:
            continue
        if low in skip or low.startswith("http"):
            continue
        if re.match(r"^[\d\s\-+/]+$", ln):
            continue
        if caps_name.match(ln.strip()) and 6 < len(ln) < 60:
            return ln.strip().title() if ln.isupper() else ln.strip()
        if title_name.match(ln.strip()):
            return ln.strip()
    for ln in lines[:6]:
        if EMAIL_RE.search(ln) or "@" in ln:
            continue
        if 2 <= len(ln.split()) <= 6 and len(ln) < 55:
            return ln.strip()
    return "Candidate"


def _skill_lines_to_entries(section_lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in section_lines:
        t = ln.strip()
        if not t:
            continue
        lead = t.lstrip()
        if lead[:1] in "•-*–●◦▪►" or re.match(r"^[\[\(]?\d+[\]\).]\s+", lead):
            out.append(lead.lstrip("•-*–●◦▪►").lstrip("0123456789.)]} ").strip())
            continue
        if ":" in t and len(t.split(":")[0]) < 28:
            _, right = t.split(":", 1)
            for p in re.split(r"[,;|]", right):
                p = p.strip()
                if p:
                    out.append(p)
        else:
            out.append(t)
    return [x for x in out if len(x) > 1]


def _is_bullet_line(line: str) -> bool:
    s = line.lstrip()
    if not s:
        return False
    if s[0] in "•*–—\u2022\u00b7\ufffd":
        return True
    if re.match(r"^\d+[\).\]]\s+", s):
        return True
    return False


def _strip_bullet(line: str) -> str:
    return re.sub(
        r"^\s*(?:[•\*\-\u2013\u2014\u2022\u00b7\ufffd]|\d+[\).\]]\s+)+",
        "",
        line,
    ).strip()


def _institution_year_span(ln: str) -> tuple[str, str] | None:
    ln = ln.strip()
    m = _DATE_SPAN.search(ln)
    if m and m.end() == len(ln.rstrip()):
        return ln[: m.start()].strip(), m.group(1).strip()
    m2 = _YEAR_ONLY_SPAN.match(ln)
    if m2:
        return m2.group(1).strip(), f"{m2.group(2)} – {m2.group(3)}"
    return None


def _split_degree_location(degree_line: str) -> tuple[str, str]:
    t = degree_line.strip()
    if t.endswith(", India"):
        left = t[: -len(", India")].strip()
        m_state = re.search(
            r"^(?P<deg>.+)\s+(?P<st>New Delhi|Andhra Pradesh|Tamil Nadu|Uttar Pradesh|"
            r"Karnataka|Maharashtra|Telangana|Dubai)\s*$",
            left,
            re.I,
        )
        if m_state:
            return m_state.group("deg").strip(), f"{m_state.group('st')}, India"
        return left, "India"
    mloc = re.search(r",\s*(India|UAE|United Arab Emirates|USA)\s*$", t, re.I)
    if mloc and mloc.start() > 3:
        return t[: mloc.start()].strip(), t[mloc.start() :].lstrip(", ").strip()
    for sep_suffix in (
        " Andhra Pradesh, India",
        " New Delhi, India",
        " Tamil Nadu, India",
        " Uttar Pradesh, India",
        " Dubai, UAE",
    ):
        if t.endswith(sep_suffix):
            return t[: -len(sep_suffix)].strip(), sep_suffix.strip()
    if t.endswith(" India"):
        return t[: -len(" India")].strip(), "India"
    return t, ""


def _normalize_skill_tokens(raw_skills: list[str]) -> list[str]:
    out: list[str] = []
    pending = ""
    for s in raw_skills:
        s = s.strip()
        if not s:
            continue
        if pending:
            s = pending + " " + s
            pending = ""
        open_c, close_c = s.count("("), s.count(")")
        if open_c > close_c:
            pending = s
            continue
        out.append(re.sub(r"\s+", " ", s))
    if pending:
        out.append(pending + (")" if pending.count("(") > pending.count(")") else ""))
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq[:100]


def _education_pair_blocks(section_lines: list[str]) -> list[EducationItem]:
    out: list[EducationItem] = []
    sl = [x.strip() for x in section_lines if x.strip()]
    i = 0
    while i < len(sl):
        ln = sl[i]
        if ln.lower().startswith("relevant coursework"):
            break
        if _is_bullet_line(ln):
            i += 1
            continue
        span_info = _institution_year_span(ln)
        if not span_info:
            i += 1
            continue
        inst, year_span = span_info
        if len(inst) < 4:
            i += 1
            continue
        if i + 1 >= len(sl):
            break
        nxt = sl[i + 1]
        if _is_bullet_line(nxt):
            i += 1
            continue
        if nxt.lower().startswith("relevant coursework"):
            break
        deg, field = _split_degree_location(nxt)
        out.append(
            EducationItem(
                institution=inst,
                degree=deg,
                field=field,
                year=year_span,
            )
        )
        i += 2
    return out


def _education_legacy_from_lines(section_lines: list[str]) -> list[EducationItem]:
    edu: list[EducationItem] = []
    buf: list[str] = []
    year_re = re.compile(r"\b(?:19|20)\d{2}\b")

    def flush():
        nonlocal buf
        if not buf:
            return
        year = ""
        for ln in buf:
            ym = year_re.search(ln)
            if ym:
                year = ym.group(0)
        deg = ""
        inst = ""
        field = ""
        for ln in buf:
            low = ln.lower()
            if any(d in low for d in ("b.tech", "b.e", "bachelor", "m.tech", "master", "m.s", "ph.d", "diploma", "b.sc", "m.sc", "mba")):
                deg = ln
            elif len(ln) > 8 and not year_re.search(ln) and not deg and (
                "university" in low or "institute" in low or "college" in low
            ):
                inst = ln
            elif len(ln) > 3 and not deg:
                field = ln
        if deg or inst or field:
            edu.append(
                EducationItem(
                    institution=inst or "—",
                    degree=deg or "",
                    field=field or "",
                    year=year or "",
                )
            )
        buf = []

    for ln in section_lines:
        t = ln.strip()
        if t.startswith("•") or re.match(r"^\d+\.", t):
            flush()
            buf = [t.lstrip("•-*0123456789.) ").strip()]
        elif len(t) < 160:
            buf.append(t)
            if len(buf) >= 5:
                flush()
        else:
            flush()
            buf = [t]
    flush()
    return edu


def _education_from_lines(section_lines: list[str]) -> list[EducationItem]:
    paired = _education_pair_blocks(section_lines)
    return paired if paired else _education_legacy_from_lines(section_lines)


def _experience_legacy_from_lines(section_lines: list[str]) -> list[ExperienceItem]:
    bullets: list[str] = []
    company = ""
    title = ""
    for ln in section_lines:
        t = ln.strip()
        if not t:
            continue
        lead = t.lstrip()
        if lead[:1] in "•-*–●" or re.match(r"^\d+\.", lead):
            bullets.append(lead.lstrip("•-*–0123456789.) ").strip())
        elif "|" in t and len(t) < 100:
            parts = [p.strip() for p in t.split("|", 1)]
            title = parts[0]
            if len(parts) > 1:
                company = parts[1]
        elif not bullets and len(t) < 90 and (t.endswith("Ltd") or "Pvt" in t or "Inc" in t):
            company = t
        elif not bullets and len(t) < 90 and not title:
            title = t
    if not bullets:
        bullets = [ln for ln in section_lines if len(ln) > 15][:15]
    return [
        ExperienceItem(
            company=company or "—",
            title=title or "",
            start_date="",
            end_date="",
            bullets=bullets[:24] or ["See resume for details."],
        )
    ]


def _experience_multi_from_lines(section_lines: list[str]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    cur: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal cur
        if cur and (cur.get("company") or cur.get("bullets")):
            bl = [b for b in (cur.get("bullets") or []) if b]
            items.append(
                ExperienceItem(
                    company=cur.get("company") or "—",
                    title=cur.get("title") or "",
                    start_date=cur.get("start_date") or "",
                    end_date=cur.get("end_date") or "",
                    bullets=bl[:24] if bl else ["See resume for details."],
                )
            )
        cur = None

    for raw in section_lines:
        t = raw.strip()
        if not t:
            continue
        if _is_bullet_line(t):
            if cur is None:
                cur = {"company": "", "title": "", "start_date": "", "end_date": "", "bullets": []}
            cur.setdefault("bullets", []).append(_strip_bullet(t))
            continue
        m = _COMPANY_AND_DATES.match(t)
        if m:
            flush()
            cur = {
                "company": m.group(1).strip(),
                "title": "",
                "start_date": m.group(2).strip(),
                "end_date": m.group(3).strip(),
                "bullets": [],
            }
            continue
        if cur is not None and not cur.get("title"):
            cur["title"] = t
            continue
        if cur is not None and cur.get("title") and not _COMPANY_AND_DATES.match(t) and not _is_bullet_line(t):
            bl = cur.setdefault("bullets", [])
            if bl:
                bl[-1] = (bl[-1] + " " + t).strip()
            else:
                bl.append(t)
            continue
    flush()
    return items if items else _experience_legacy_from_lines(section_lines)


def _experience_from_lines(section_lines: list[str]) -> list[ExperienceItem]:
    return _experience_multi_from_lines(section_lines)


_PROJECT_HEADER_RE = re.compile(
    rf"^(.+?)\s*\|\s*(.+?)\s+({_MONTH_SHORT}\s+\d{{4}})\s*$",
    re.I,
)


def _projects_from_lines(section_lines: list[str]) -> list[ProjectItem]:
    items: list[ProjectItem] = []
    cur: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal cur
        if not cur:
            return
        name = (cur.get("name") or "").strip()
        if not name or name.lower() in ("technical", "skills"):
            cur = None
            return
        b = [x for x in (cur.get("bullets") or []) if x]
        desc = (cur.get("description") or "").strip()
        if b:
            desc = (desc + "\n" + "\n".join(f"• {x}" for x in b)).strip()
        items.append(
            ProjectItem(
                name=name or "Project",
                description=desc,
                tech_stack=list(cur.get("tech_stack") or []),
                link=None,
            )
        )
        cur = None

    for raw in section_lines:
        ln = raw.strip()
        if not ln:
            continue
        if ln.lower() in ("technical",) and not _PROJECT_HEADER_RE.match(ln):
            continue
        if _is_bullet_line(ln):
            if cur is None:
                cur = {"name": "", "description": "", "tech_stack": [], "bullets": []}
            cur.setdefault("bullets", []).append(_strip_bullet(ln))
            continue
        m = _PROJECT_HEADER_RE.match(ln)
        if m:
            flush()
            tech_part = m.group(2).strip()
            toks = [x.strip() for x in re.split(r"[,，]", tech_part) if x.strip()]
            cur = {
                "name": m.group(1).strip(),
                "tech_stack": toks,
                "description": "",
                "bullets": [],
            }
            continue
        if cur and not _is_bullet_line(ln):
            cur["description"] = (cur.get("description") or "") + " " + ln
    flush()
    return items


def _enrich_contact_from_header(
    header_lines: list[str], cleaned: str, base: ContactBlock
) -> ContactBlock:
    d = base.model_dump()
    blob = "\n".join(header_lines[:10])
    if not d.get("email"):
        e = _extract_email(blob) or _extract_email(cleaned)
        if e:
            d["email"] = e
    if not d.get("phone"):
        p = _extract_phone(blob) or _extract_phone(cleaned)
        if p:
            d["phone"] = p
    li0 = d.get("linkedin") or _extract_linkedin(blob) or _extract_linkedin(cleaned)
    if li0:
        li = str(li0).strip()
        if not li.lower().startswith("http"):
            li = f"https://{li.lstrip('/')}"
        d["linkedin"] = li
    if not d.get("location"):
        for ln in header_lines[:10]:
            if re.search(r",\s*(India|USA|UAE)\b", ln, re.I) and len(ln) < 100:
                d["location"] = re.sub(r"\s+", " ", ln.strip())
                break
    if not d.get("location"):
        loc = _extract_location(cleaned)
        if loc:
            d["location"] = loc
    return ContactBlock.model_validate(d)


def _strip_contact_noise_from_summary(summary: str, contact: ContactBlock) -> str:
    s = summary
    if contact.email:
        s = s.replace(contact.email, " ")
    if contact.phone:
        s = s.replace(contact.phone, " ").replace(re.sub(r"\s+", "", contact.phone), " ")
    if contact.linkedin:
        s = re.sub(re.escape(contact.linkedin), " ", s, flags=re.I)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"linkedin\s*www\.\S*", " ", s, flags=re.I)
    s = EMAIL_RE.sub(" ", s)
    s = PHONE_RE.sub(" ", s)
    s = re.sub(r"(?i)(?:♂|phone|tel\.)\s*\+?\d[\d\s\-]{8,}\d", " ", s)
    s = re.sub(r"\b(linkedin|github|phone|email)\S*", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+\b(Education|Skills|Experience|Technical)\s*$", "", s, flags=re.I)
    if len(s) < 20:
        return ""
    return s[:2000]


def heuristic_resume_structure(raw: str) -> dict[str, Any]:
    cleaned = clean_resume_text(raw)
    lines = _lines(cleaned)
    email = _extract_email(cleaned)
    phone = _extract_phone(cleaned)
    linkedin = _extract_linkedin(cleaned)
    github = _extract_github(cleaned)
    location = _extract_location(cleaned)
    name = _infer_name(lines)

    sections = _split_sections(lines)
    other_lines = sections.get("other") or []

    summary_lines = sections.get("summary") or []
    summary = " ".join(summary_lines[:16]) if summary_lines else ""

    exp_items = _experience_from_lines(sections.get("experience") or [])
    edu_items = _education_from_lines(sections.get("education") or [])
    proj_items = _projects_from_lines(sections.get("projects") or [])

    skill_lines = sections.get("skills") or []
    technical = _normalize_skill_tokens(_skill_lines_to_entries(skill_lines) or skill_lines)

    cert_section = sections.get("certifications") or []
    certifications = [ln.strip() for ln in cert_section if ln.strip()][:24]

    contact = ContactBlock(
        name=name,
        email=email,
        phone=phone,
        linkedin=linkedin,
        github=github,
        location=location,
    )
    contact = _enrich_contact_from_header(other_lines, cleaned, contact)
    summary = _strip_contact_noise_from_summary(summary, contact)
    if not summary.strip() and exp_items:
        parts: list[str] = []
        for e in exp_items[:3]:
            if e.title and e.company and e.company != "—":
                parts.append(f"{e.title} at {e.company}.")
            elif e.title:
                parts.append(f"{e.title}.")
            elif e.company and e.company != "—":
                parts.append(f"Experience at {e.company}.")
        if exp_items[0].bullets:
            parts.append(exp_items[0].bullets[0][:400])
        summary = " ".join(parts)[:1200]

    has_doc_summary = bool(summary_lines)
    resume = ResumeSchema(
        contact=contact,
        summary=summary,
        summary_origin="document" if has_doc_summary else "model",
        experience=exp_items,
        education=edu_items,
        skills=SkillsBlock(
            technical=technical or [],
            soft=[],
            tools=[],
            certifications=certifications,
        ),
        projects=proj_items,
    )
    return resume.model_dump()


def _enrich_contact_from_text(dumped: dict[str, Any], cleaned_text: str) -> None:
    c = dumped.get("contact") or {}
    if not c.get("email"):
        e = _extract_email(cleaned_text)
        if e:
            c["email"] = e
    p_rx = _extract_phone(cleaned_text)
    p_llm = (c.get("phone") or "").strip()
    if p_rx and (_phone_value_suspicious(p_llm) or not p_llm):
        c["phone"] = p_rx
    elif not c.get("phone") and p_rx:
        c["phone"] = p_rx
    if not c.get("linkedin"):
        li = _extract_linkedin(cleaned_text)
        if li:
            c["linkedin"] = li
    if not c.get("github"):
        g = _extract_github(cleaned_text)
        if g:
            c["github"] = g
    if not c.get("location"):
        loc = _extract_location(cleaned_text)
        if loc:
            c["location"] = loc
    nm = (c.get("name") or "").strip()
    if (not nm) or (nm.lower() in _BAD_LLM_CONTACT_NAMES) or (len(nm) < 2):
        inferred = _infer_name_near_contact(cleaned_text)
        if inferred:
            c["name"] = inferred
    dumped["contact"] = c


def has_summary_section_heading(text: str) -> bool:
    """True if the resume text has a Summary / Profile style section header."""
    return bool(
        re.search(
            r"(?im)^\s*(professional\s+summary|summary|profile|objective|about\s+me)\s*:?\s*$",
            text,
        )
    )


def set_summary_origin_from_text(parsed: dict[str, Any], cleaned_text: str) -> None:
    """Mark whether the summary was taken from a document section vs model-generated."""
    parsed["summary_origin"] = "document" if has_summary_section_heading(cleaned_text) else "model"


_GPA_IN_LINE = re.compile(r"GPA\s*:\s*([\d.]+\s*/\s*\d+)", re.I)


def fill_education_gpa_from_text(parsed: dict[str, Any], cleaned_text: str) -> None:
    """Attach GPA when it appears on the institution line or within a few lines below (common in IIT-style PDFs)."""
    edu_list = parsed.get("education")
    if not isinstance(edu_list, list):
        return
    lines = [ln.rstrip() for ln in cleaned_text.splitlines()]
    for edu in edu_list:
        if not isinstance(edu, dict):
            continue
        if edu.get("gpa"):
            continue
        inst = (edu.get("institution") or "").strip()
        if len(inst) < 6:
            continue
        key = inst[:32].lower()
        for i, ln in enumerate(lines):
            if key not in ln.lower():
                continue
            window = "\n".join(lines[i : min(len(lines), i + 6)])
            m = _GPA_IN_LINE.search(window)
            if m:
                edu["gpa"] = re.sub(r"\s+", "", m.group(1))
                break


def contact_location_fallback(parsed: dict[str, Any], cleaned_text: str) -> None:
    """Infer city/country when the PDF omits a dedicated location but names a campus."""
    c = parsed.get("contact")
    if not isinstance(c, dict):
        return
    if (c.get("location") or "").strip():
        return
    low = cleaned_text.lower()
    if "kharagpur" in low and "iit" in low:
        c["location"] = "Kharagpur, India"
    elif "haldwani" in low:
        c["location"] = "Haldwani, India"


async def llm_parse_resume(cleaned_text: str) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    schema = ResumeSchema.model_json_schema()
    system = (
        "You convert raw resume text into JSON for ResumeSchema. "
        "Use ONLY information present in the text — never invent employers, degrees, or dates. "
        "contact.name must be the person's real name only — never a section title (e.g. not 'Internship', 'Education', 'Summary'). "
        "contact.linkedin and contact.github must be full https URLs when they appear in the text. "
        "Use standard brand spellings when they appear in the text: DocuSign, SigTuple, SymphonyAI, LangChain, FastAPI, CrewAI (not split with extra spaces). "
        "summary: 2–5 professional sentences ONLY — no phone numbers, emails, URLs, symbols, cities alone, or section titles. "
        "If the document has no summary/profile section, still output a concise summary field from stated roles and education. "
        "skills.technical: flat list of concise tokens; merge fragmented parentheticals (e.g. VectorDB + ChromaDB/FAISS/Pinecone). "
        "education: all degrees/institutions/years; include gpa when stated (e.g. GPA: 8.69/10). "
        "experience: real company names and titles when stated; otherwise use '—' for company and put bullets under one role."
    )
    user_text = cleaned_text[:14_000]
    resp = await client.chat.completions.create(
        model=settings.openai_parse_model,
        messages=[
            {"role": "system", "content": system + f"\nTop-level keys: {list(schema.get('properties', {}).keys())}"},
            {"role": "user", "content": user_text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    text = resp.choices[0].message.content or "{}"
    data = json.loads(text)
    resume = ResumeSchema.model_validate(data)
    dumped = resume.model_dump()
    _enrich_contact_from_text(dumped, cleaned_text)
    contact = ContactBlock.model_validate(dumped.get("contact") or {})
    dumped["summary"] = _strip_contact_noise_from_summary(dumped.get("summary") or "", contact)
    return dumped


def _extract_bytes_to_text(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return parse_pdf(data)
    if lower.endswith(".docx"):
        return parse_docx(data)
    return parse_txt(data)


async def parse_upload(filename: str, data: bytes) -> dict[str, Any]:
    from app.services.resume_finalize import finalize_resume

    raw = _extract_bytes_to_text(filename, data)
    cleaned = clean_resume_text(raw)
    draft = heuristic_resume_structure(raw)
    if settings.openai_api_key:
        try:
            parsed = await llm_parse_resume(cleaned)
        except Exception:
            parsed = draft
        out = await finalize_resume(parsed, cleaned)
    else:
        out = await finalize_resume(draft, cleaned)
    out["_resumeiq_cleaned"] = cleaned[:32_000]
    return out
