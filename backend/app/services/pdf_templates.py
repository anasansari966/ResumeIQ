import copy
import re
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _norm_ws(s: str) -> str:
    t = (s or "").replace("\u200b", "").replace("\ufeff", "")
    t = re.sub(r"[\r\n\t]+", " ", t)
    t = re.sub(r" +", " ", t)
    return t.strip()


def _sanitize_display_text(s: str) -> str:
    """Strip PDF extraction junk before ReportLab / XML escape."""
    t = _norm_ws(str(s or ""))
    t = re.sub(r"\(cid:\d+\)", " ", t)
    t = t.replace("linkedinwww.", "https://www.linkedin.").replace("linkedin www.", "https://www.linkedin.")
    t = re.sub(r"/envel\w*", "", t, flags=re.I)
    t = re.sub(r"/linkedin\s*", " ", t, flags=re.I)
    t = re.sub(r"(?i)phone\s*\+?", " +", t)
    t = re.sub(r"[■▪●◆◇□✓✔♂♀]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # PDF icon glue: "pe" + long local-part email (e.g. envelope + "p" + user@gmail)
    t = re.sub(
        r"(?i)\bpe([a-z][a-z0-9.+-]{6,}@[\w-]+\.[\w.-]+)\b",
        r"\1",
        t,
    )
    return t.strip()


def _is_contact_garbage_summary(s: str) -> bool:
    if not s or len(s) < 24:
        return False
    low = s.lower()
    hits = sum(
        1
        for x in (
            "@",
            "linkedin.com",
            "+91",
            "+1",
            "phone",
            "gmail.com",
            "hotmail.",
            "/envel",
            "■",
        )
        if x in low
    )
    return hits >= 2


def _short_url(url: str) -> str:
    u = _sanitize_display_text(url)
    if "linkedin.com/" in u.lower():
        u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I).rstrip("/")
        return u
    return u


def _clean_resume_for_pdf(raw: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(raw)
    c = data.get("contact") or {}
    for k in ("name", "email", "phone", "location", "linkedin", "github"):
        if c.get(k):
            c[k] = _sanitize_display_text(str(c[k]))
    data["contact"] = c

    summary = _sanitize_display_text(str(data.get("summary") or ""))
    if _is_contact_garbage_summary(summary):
        summary = ""
    data["summary"] = summary

    ex_out: list[dict[str, Any]] = []
    for e in data.get("experience") or []:
        if not isinstance(e, dict):
            continue
        company = _sanitize_display_text(str(e.get("company") or ""))
        title = _sanitize_display_text(str(e.get("title") or ""))
        comp_low = company.lower()
        bullets_raw = e.get("bullets") or []
        bullets: list[str] = []
        for b in bullets_raw:
            bt = _sanitize_display_text(str(b))
            bt = _norm_ws(bt)
            if len(bt) < 4:
                continue
            lowb = bt.lower()
            if lowb.startswith("delivered outcomes relevant to ") and "cross-functional" in lowb:
                continue
            bullets.append(bt)
        if bogus := (
            (not company or "see full" in comp_low or company in ("—", "-"))
            and not title
            and not bullets
        ):
            continue
        if (not company or company in ("—", "-")) and title and bullets:
            company = company or "—"
        if not title and not bullets and not company:
            continue
        ex_out.append(
            {
                "company": company or "—",
                "title": title,
                "start_date": _sanitize_display_text(str(e.get("start_date") or "")),
                "end_date": _sanitize_display_text(str(e.get("end_date") or "")),
                "bullets": bullets,
            }
        )
    data["experience"] = ex_out

    edu_out: list[dict[str, Any]] = []
    for edu in data.get("education") or []:
        if not isinstance(edu, dict):
            continue
        edu_out.append(
            {
                "degree": _sanitize_display_text(str(edu.get("degree") or "")),
                "field": _sanitize_display_text(str(edu.get("field") or "")),
                "institution": _sanitize_display_text(str(edu.get("institution") or "")),
                "year": _sanitize_display_text(str(edu.get("year") or "")),
            }
        )
    data["education"] = edu_out

    sk = data.get("skills") or {}
    tech = [_sanitize_display_text(str(x)) for x in (sk.get("technical") or []) if str(x).strip()]
    tech = [t for t in tech if t]
    data["skills"] = {**sk, "technical": tech}

    pr_out: list[dict[str, Any]] = []
    for p in data.get("projects") or []:
        if not isinstance(p, dict):
            continue
        pr_out.append(
            {
                "name": _sanitize_display_text(str(p.get("name") or "")),
                "description": _sanitize_display_text(str(p.get("description") or "")),
            }
        )
    data["projects"] = pr_out
    return data


def _default_pdf_theme() -> dict[str, Any]:
    """Single fallback layout when exporting PDF without a Word template."""
    accent = colors.HexColor("#0e7490")
    return {
        "accent": accent,
        "name_align": TA_LEFT,
        "name_font": "Helvetica-Bold",
        "body_font": "Helvetica",
        "name_size": 22,
        "margin_x": 0.72 * inch,
        "rule_pt": 1.0,
    }


def _styles(theme: dict[str, Any]):
    ss = getSampleStyleSheet()
    accent = theme["accent"]
    nf, bf = theme["name_font"], theme["body_font"]
    al = theme["name_align"]

    name_style = ParagraphStyle(
        "name",
        parent=ss["Title"],
        fontName=nf,
        fontSize=theme["name_size"],
        textColor=accent,
        alignment=al,
        spaceAfter=8,
        leading=theme["name_size"] + 4,
    )
    head = ParagraphStyle(
        "h",
        parent=ss["Heading2"],
        fontName=nf,
        fontSize=12,
        textColor=accent,
        spaceBefore=14,
        spaceAfter=6,
        leading=14,
        borderWidth=0,
        borderPadding=(0, 0, 2, 0),
        borderColor=accent,
    )
    body = ParagraphStyle(
        "b",
        parent=ss["BodyText"],
        fontName=bf,
        fontSize=10,
        leading=13.5,
        alignment=TA_LEFT,
        spaceAfter=3,
    )
    small = ParagraphStyle(
        "s",
        parent=body,
        fontSize=9,
        textColor=colors.HexColor("#4b5563"),
        leading=12,
        alignment=al,
    )
    bull = ParagraphStyle(
        "bull",
        parent=body,
        leftIndent=14,
        firstLineIndent=-14,
        spaceBefore=1,
        spaceAfter=4,
        bulletIndent=0,
    )
    job_head = ParagraphStyle(
        "jobh",
        parent=body,
        fontName=nf,
        fontSize=10.5,
        leading=13,
        spaceBefore=6,
        spaceAfter=4,
        textColor=colors.black,
    )
    return name_style, head, body, small, bull, job_head, accent


def _escape(t: str) -> str:
    return (
        (t or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _skills_flowables(
    technical: list[str],
    inner_width: float,
    head: ParagraphStyle,
    body: ParagraphStyle,
) -> list[Any]:
    """Dense skills: comma flow for short lists; two-column table for long lists."""
    if not technical:
        return []
    out: list[Any] = [Paragraph("Skills", head)]
    esc = [_escape(_sanitize_display_text(t)) for t in technical if str(t).strip()]
    if not esc:
        return []
    if len(esc) <= 8:
        out.append(Paragraph(", ".join(esc), body))
        return out
    mid = (len(esc) + 1) // 2
    col_w = max(120, (inner_width - 12) / 2)
    left = ", ".join(esc[:mid])
    right = ", ".join(esc[mid:])
    tbl = Table([[Paragraph(left, body), Paragraph(right, body)]], colWidths=[col_w, col_w])
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ]
        )
    )
    out.append(tbl)
    return out


def _format_skills_lines(technical: list[str]) -> list[str]:
    """One Paragraph per line; tokens like 'Languages: Python, R' become bold label + body."""
    if not technical:
        return []
    chunks: list[str] = []
    for tok in technical:
        m = re.match(r"^([A-Za-z /&]+):\s*(.+)$", tok)
        if m and len(m.group(1)) < 22:
            label, rest = m.group(1).strip(), m.group(2).strip()
            chunks.append(f"<b>{_escape(label)}:</b> {_escape(rest)}")
        else:
            chunks.append(_escape(tok))
    return chunks or [_escape(", ".join(technical))]


def build_pdf(resume_json: dict[str, Any], template_id: str = "") -> bytes:
    """Render a simple PDF. ``template_id`` is ignored; kept for call-site compatibility."""
    _ = template_id
    data = _clean_resume_for_pdf(resume_json)
    th = _default_pdf_theme()
    name_style, head, body, small, bull, job_head, accent = _styles(th)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=th["margin_x"],
        rightMargin=th["margin_x"],
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
        title="Resume",
    )
    story: list[Any] = []
    c = data.get("contact") or {}
    inner_w = LETTER[0] - 2 * th["margin_x"]

    story.append(Paragraph(_escape(c.get("name") or "Candidate"), name_style))

    if c.get("location"):
        story.append(Paragraph(_escape(_sanitize_display_text(c["location"])), small))
    contact_bits = [
        _escape(_sanitize_display_text(x))
        for x in (c.get("email"), c.get("phone"))
        if x and str(x).strip()
    ]
    if contact_bits:
        story.append(Paragraph(" · ".join(contact_bits), small))
    link_bits = []
    if c.get("linkedin"):
        link_bits.append(_escape(_short_url(c["linkedin"])))
    if c.get("github"):
        link_bits.append(_escape(_sanitize_display_text(c["github"])))
    if link_bits:
        story.append(Paragraph(" · ".join(link_bits), small))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=th["rule_pt"], color=accent, spaceAfter=12))

    if data.get("summary"):
        story.append(Paragraph("Summary", head))
        story.append(Paragraph(_escape(data["summary"]), body))
        story.append(Spacer(1, 6))

    exps = data.get("experience") or []
    if exps:
        story.append(Paragraph("Experience", head))
        for exp in exps:
            title = _escape(exp.get("title") or "")
            company = _escape(exp.get("company") or "")
            sd, ed = exp.get("start_date") or "", exp.get("end_date") or ""
            dates = ""
            if sd or ed:
                dates = f"{_escape(sd)} – {_escape(ed or 'Present')}"
            if title and company and company != "—":
                hdr = f"<b>{title}</b> &nbsp;<font color='#0e7490'>•</font>&nbsp; <i>{company}</i>"
            elif title:
                hdr = f"<b>{title}</b>"
            elif company:
                hdr = f"<b>{company}</b>"
            else:
                hdr = "<b>Experience</b>"
            if dates:
                hdr += f' &nbsp;<font size="9" color="#6b7280">({dates})</font>'
            story.append(Paragraph(hdr, job_head))
            for b in exp.get("bullets") or []:
                story.append(Paragraph(f"• {_escape(b)}", bull))
            story.append(Spacer(1, 4))

    if data.get("education"):
        story.append(Paragraph("Education", head))
        for edu in data["education"]:
            deg = _escape(edu.get("degree") or "")
            inst = _escape(edu.get("institution") or "")
            fld = _escape(edu.get("field") or "")
            yr = _escape(edu.get("year") or "")
            head_ln = f"<b>{deg}</b>" if deg else ""
            if inst:
                head_ln += (", " if head_ln else "") + f"<i>{inst}</i>"
            tail = " · ".join(filter(None, [fld, yr]))
            if tail:
                head_ln += f" <font color='#6b7280'>({tail})</font>"
            story.append(Paragraph(head_ln or "—", body))

    tech = (data.get("skills") or {}).get("technical") or []
    story.extend(_skills_flowables(tech, inner_w, head, body))

    if data.get("projects"):
        story.append(Spacer(1, 4))
        story.append(Paragraph("Projects", head))
        for i, p in enumerate(data["projects"]):
            if i:
                story.append(Spacer(1, 8))
            nm = _escape(p.get("name") or "")
            desc = _escape(p.get("description") or "")
            if nm:
                story.append(Paragraph(f"<b>{nm}</b>", job_head))
            if desc:
                for chunk in desc.split("\n"):
                    chunk = _norm_ws(chunk)
                    if chunk:
                        story.append(Paragraph(chunk, body))

    doc.build(story)
    return buf.getvalue()
