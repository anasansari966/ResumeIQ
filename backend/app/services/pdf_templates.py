import copy
import re
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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


def _default_pdf_theme(template_id: str = "") -> dict[str, Any]:
    """Template-aware fallback layout when LaTeX/Word renderers are unavailable."""
    tid = (template_id or "").lower()
    profile = "ats"
    accent_hex = "#0e7490"
    muted_hex = "#4b5563"
    name_align = TA_LEFT
    name_font = "Helvetica-Bold"
    body_font = "Helvetica"
    name_size = 22
    body_size = 10
    margin_x = 0.72 * inch
    rule_pt = 1.0
    section_order = ["summary", "experience", "education", "skills", "projects"]

    if "zip_" in tid:
        if "chicago" in tid:
            profile = "executive"
            accent_hex = "#1e3a8a"
            muted_hex = "#475569"
            name_align = TA_LEFT
            body_font = "Times-Roman"
            name_size = 24
            margin_x = 0.78 * inch
            section_order = ["summary", "experience", "skills", "education", "projects"]
        elif "milano" in tid:
            profile = "slate"
            accent_hex = "#607d8b"
            muted_hex = "#455a64"
            body_size = 9.5
        elif "easy" in tid:
            profile = "web"
            accent_hex = "#ad6452"
            section_order = ["summary", "experience", "education", "skills", "projects"]
        elif "classic" in tid:
            profile = "emerald"
            accent_hex = "#548135"
            muted_hex = "#374151"
            margin_x = 0.68 * inch
    elif "coral" in tid or "web_" in tid:
        profile = "web"
        accent_hex = "#eb5757"
        section_order = ["summary", "experience", "skills", "education", "projects"]
    elif "executive" in tid:
        profile = "executive"
        accent_hex = "#1e3a8a"
        muted_hex = "#475569"
        name_align = TA_LEFT
        body_font = "Times-Roman"
        name_size = 24
        margin_x = 0.78 * inch
        section_order = ["summary", "experience", "skills", "education", "projects"]
    elif "emerald" in tid:
        profile = "emerald"
        accent_hex = "#047857"
        section_order = ["summary", "experience", "education", "projects", "skills"]
    elif "data" in tid:
        profile = "data"
        accent_hex = "#0f766e"
        muted_hex = "#374151"
        margin_x = 0.62 * inch
        body_size = 9.5
        section_order = ["skills", "experience", "projects", "education", "summary"]
    elif "slate" in tid:
        profile = "slate"
        accent_hex = "#334155"
        muted_hex = "#6b7280"
        body_size = 9.5
        section_order = ["summary", "experience", "skills", "education", "projects"]
    elif "robotics" in tid or "research" in tid:
        profile = "robotics"
        accent_hex = "#0ea5e9"
        muted_hex = "#374151"
        section_order = ["summary", "experience", "projects", "education", "skills"]
    elif "ats" in tid:
        profile = "ats"
        accent_hex = "#0e7490"
        section_order = ["summary", "experience", "education", "skills", "projects"]

    accent = colors.HexColor(accent_hex)
    return {
        "profile": profile,
        "accent": accent,
        "accent_hex": accent_hex,
        "muted_hex": muted_hex,
        "name_align": name_align,
        "name_font": name_font,
        "body_font": body_font,
        "name_size": name_size,
        "body_size": body_size,
        "margin_x": margin_x,
        "rule_pt": rule_pt,
        "section_order": section_order,
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
    body_size = float(theme.get("body_size") or 10)
    body = ParagraphStyle(
        "b",
        parent=ss["BodyText"],
        fontName=bf,
        fontSize=body_size,
        leading=body_size + 3.5,
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


class _SkillChips(Flowable):
    """Wrapping rounded skill chips used by the clean preview-style PDF."""

    def __init__(self, skills: list[str], accent_hex: str, fill_hex: str):
        super().__init__()
        self.skills = skills
        self.accent_hex = accent_hex
        self.fill_hex = fill_hex
        self.font_name = "Helvetica-Bold"
        self.font_size = 6.8
        self.line_height = 19.0
        self._layout: list[tuple[float, float, float, str]] = []

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        del avail_height
        x = 0.0
        row = 0
        self._layout = []
        for raw in self.skills:
            label = _sanitize_display_text(raw)
            if not label:
                continue
            chip_w = min(avail_width, stringWidth(label, self.font_name, self.font_size) + 15)
            if x and x + chip_w > avail_width:
                row += 1
                x = 0.0
            self._layout.append((x, row * self.line_height, chip_w, label))
            x += chip_w + 5
        rows = (max((int(y / self.line_height) for _, y, _, _ in self._layout), default=-1) + 1)
        self.width = avail_width
        self.height = max(self.line_height, rows * self.line_height)
        return avail_width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFont(self.font_name, self.font_size)
        canvas.setFillColor(colors.HexColor(self.accent_hex))
        for x, row_y, chip_w, label in self._layout:
            y = self.height - row_y - 14
            canvas.setFillColor(colors.HexColor(self.fill_hex))
            canvas.roundRect(x, y - 1, chip_w, 14, 7, stroke=0, fill=1)
            canvas.setFillColor(colors.HexColor(self.accent_hex))
            canvas.drawCentredString(x + chip_w / 2, y + 3, label)
        canvas.restoreState()


def _soft_accent(accent_hex: str, ratio: float = 0.84) -> str:
    raw = accent_hex.lstrip("#")
    if len(raw) != 6:
        return "#d9efec"
    rgb = [int(raw[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = [round(value + (255 - value) * ratio) for value in rgb]
    return "#" + "".join(f"{value:02x}" for value in mixed)


def _rounded_card(contents: list[Any], width: float, *, fill: str = "#ffffff", border: str = "#e5eceb") -> Table:
    card = Table([[contents]], colWidths=[width], cornerRadii=[10])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fill)),
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor(border)),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return card


def _build_clean_structured_pdf(data: dict[str, Any], theme: dict[str, Any]) -> bytes:
    """Match the clean live preview with a structured header, cards, chips, and two columns."""
    accent_hex = str(theme.get("accent_hex") or "#0f766e")
    if not accent_hex.startswith("#"):
        accent_hex = f"#{accent_hex}"
    accent = colors.HexColor(accent_hex)
    accent_soft = _soft_accent(accent_hex, 0.82)
    accent_wash = _soft_accent(accent_hex, 0.92)
    ink = colors.HexColor("#102a2a")
    muted = colors.HexColor("#526766")
    border = "#e3ecea"

    ss = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "clean-name",
        parent=ss["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=23,
        textColor=ink,
        spaceAfter=4,
    )
    headline_style = ParagraphStyle(
        "clean-headline",
        parent=ss["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        textColor=accent,
        spaceAfter=8,
    )
    summary_style = ParagraphStyle(
        "clean-summary",
        parent=ss["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=11,
        textColor=muted,
    )
    contact_style = ParagraphStyle(
        "clean-contact",
        parent=ss["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=6.4,
        leading=8,
        alignment=TA_CENTER,
        textColor=ink,
    )
    section_style = ParagraphStyle(
        "clean-section",
        parent=ss["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9,
        textColor=accent,
        spaceBefore=2,
        spaceAfter=7,
    )
    role_style = ParagraphStyle(
        "clean-role",
        parent=ss["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.2,
        leading=11,
        textColor=ink,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "clean-meta",
        parent=ss["BodyText"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=9,
        textColor=muted,
        spaceAfter=4,
    )
    detail_style = ParagraphStyle(
        "clean-detail",
        parent=ss["BodyText"],
        fontName="Helvetica",
        fontSize=7.1,
        leading=10.2,
        textColor=muted,
        leftIndent=8,
        firstLineIndent=-8,
        spaceAfter=3,
    )
    card_title_style = ParagraphStyle(
        "clean-card-title",
        parent=role_style,
        fontSize=8.2,
        leading=10,
    )

    margin = 0.4 * inch
    inner_width = LETTER[0] - 2 * margin
    gutter = 10
    left_width = 0.64 * (inner_width - gutter)
    right_width = inner_width - gutter - left_width
    c = data.get("contact") or {}
    experience = data.get("experience") or []
    education = data.get("education") or []
    first_role = next((str(row.get("title") or "").strip() for row in experience if isinstance(row, dict)), "")
    headline = _sanitize_display_text(str(data.get("title") or first_role or "Professional Resume"))

    left_header: list[Any] = [
        Paragraph(_escape(c.get("name") or "Candidate Name"), name_style),
        Paragraph(_escape(headline), headline_style),
    ]
    if data.get("summary"):
        left_header.append(Paragraph(_escape(data["summary"]), summary_style))

    contact_cards: list[Any] = []
    contact_values = [c.get("email"), c.get("phone"), c.get("location")]
    for value in contact_values:
        clean = _sanitize_display_text(str(value or ""))
        if not clean:
            continue
        pill = Table([[Paragraph(_escape(clean), contact_style)]], colWidths=[right_width - 28], cornerRadii=[8])
        pill.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.Color(1, 1, 1, alpha=0.78)),
                    ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#dbe7e5")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        contact_cards.extend([pill, Spacer(1, 5)])

    header = Table([[left_header, contact_cards]], colWidths=[left_width + 4, right_width + gutter - 4], cornerRadii=[15])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent_soft)),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1e4e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 18),
                ("RIGHTPADDING", (0, 0), (0, 0), 12),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
                ("RIGHTPADDING", (1, 0), (1, 0), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )

    left_blocks: list[list[Any]] = []
    for idx, exp in enumerate(experience):
        if not isinstance(exp, dict):
            continue
        dates = " - ".join(filter(None, [exp.get("start_date") or "", exp.get("end_date") or ""]))
        meta = " | ".join(filter(None, [exp.get("company") or "", dates]))
        content: list[Any] = [Paragraph(_escape(exp.get("title") or "Experience role"), role_style)]
        if meta:
            content.append(Paragraph(_escape(meta), meta_style))
        for bullet in exp.get("bullets") or []:
            content.append(Paragraph(f"- {_escape(bullet)}", detail_style))
        block: list[Any] = []
        if idx == 0:
            block.append(Paragraph("E X P E R I E N C E", section_style))
        timeline = Table(
            [[Paragraph(f'<font color="{accent_hex}">&#9679;</font>', meta_style), content]],
            colWidths=[13, left_width - 35],
        )
        timeline.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        block.append(_rounded_card([timeline], left_width, border=border))
        left_blocks.append(block)

    skill_map = data.get("skills") or {}
    skill_values: list[str] = []
    for key in ("technical", "tools", "soft", "other"):
        raw = skill_map.get(key) or []
        if isinstance(raw, str):
            raw = re.split(r",|\r?\n", raw)
        skill_values.extend(str(item).strip() for item in raw if str(item).strip())
    skill_values.extend(str(item).strip() for item in (data.get("languages") or []) if str(item).strip())
    skills = list(dict.fromkeys(skill_values))

    right_blocks: list[list[Any]] = []
    if skills:
        right_blocks.append(
            [
                Paragraph("S K I L L S", section_style),
                _rounded_card([_SkillChips(skills, accent_hex, accent_soft)], right_width, border=border),
            ]
        )
    if education:
        education_content: list[Any] = []
        for idx, edu in enumerate(education):
            if not isinstance(edu, dict):
                continue
            if idx:
                education_content.append(Spacer(1, 7))
            education_content.append(Paragraph(_escape(edu.get("degree") or "Degree"), card_title_style))
            details = " | ".join(
                filter(None, [edu.get("institution") or "", edu.get("field") or "", edu.get("year") or ""])
            )
            if details:
                education_content.append(Paragraph(_escape(details), meta_style))
        right_blocks.append(
            [
                Paragraph("E D U C A T I O N", section_style),
                _rounded_card(education_content, right_width, fill="#fbfdfc", border=border),
            ]
        )

    projects = data.get("projects") or []
    for idx, project in enumerate(projects):
        if not isinstance(project, dict):
            continue
        content = [Paragraph(_escape(project.get("name") or "Project"), card_title_style)]
        if project.get("description"):
            project_detail = ParagraphStyle(
                f"clean-project-detail-{idx}",
                parent=detail_style,
                leftIndent=0,
                firstLineIndent=0,
            )
            content.append(Paragraph(_escape(project["description"]), project_detail))
        block = []
        if idx == 0:
            block.append(Paragraph("P R O J E C T S", section_style))
        block.append(_rounded_card(content, right_width, fill=accent_wash, border=border))
        right_blocks.append(block)

    buf = BytesIO()

    pdf = pdfcanvas.Canvas(buf, pagesize=LETTER)
    pdf.setTitle(f"{c.get('name') or 'Candidate'} - ATS Resume")
    pdf.setAuthor(str(c.get("name") or "ResumeIQ"))
    page_width, page_height = LETTER
    top_y = page_height - 0.36 * inch
    bottom_y = 0.38 * inch

    def paint_page() -> None:
        pdf.saveState()
        pdf.setFillColor(colors.HexColor("#f6faf9"))
        pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        pdf.setFillColor(accent)
        pdf.rect(0, page_height - 3, page_width, 3, stroke=0, fill=1)
        pdf.restoreState()

    def block_height(block: list[Any], width: float) -> float:
        total = 0.0
        for flowable in block:
            before = float(flowable.getSpaceBefore() or 0)
            after = float(flowable.getSpaceAfter() or 0)
            _, height = flowable.wrapOn(pdf, width, page_height)
            total += before + height + after
        return total + 6

    def draw_block(block: list[Any], x: float, y: float, width: float) -> float:
        for flowable in block:
            y -= float(flowable.getSpaceBefore() or 0)
            _, height = flowable.wrapOn(pdf, width, page_height)
            y -= height
            flowable.drawOn(pdf, x, y)
            y -= float(flowable.getSpaceAfter() or 0)
        return y - 6

    def draw_column(blocks: list[list[Any]], start: int, x: float, y: float, width: float) -> tuple[int, float]:
        index = start
        while index < len(blocks):
            needed = block_height(blocks[index], width)
            if y - needed < bottom_y and index > start:
                break
            if y - needed < bottom_y:
                # A single unusually large card should still make progress.
                needed = max(0, y - bottom_y)
            y = draw_block(blocks[index], x, y, width)
            index += 1
        return index, y

    left_index = 0
    right_index = 0
    page_number = 0
    while page_number == 0 or left_index < len(left_blocks) or right_index < len(right_blocks):
        paint_page()
        if page_number == 0:
            _, header_height = header.wrapOn(pdf, inner_width, page_height)
            header.drawOn(pdf, margin, top_y - header_height)
            body_top = top_y - header_height - 7
        else:
            body_top = top_y

        left_index, _ = draw_column(left_blocks, left_index, margin, body_top, left_width)
        right_index, _ = draw_column(
            right_blocks,
            right_index,
            margin + left_width + gutter,
            body_top,
            right_width,
        )
        page_number += 1
        if left_index < len(left_blocks) or right_index < len(right_blocks):
            pdf.showPage()

    pdf.save()
    return buf.getvalue()


def build_pdf(resume_json: dict[str, Any], template_id: str = "") -> bytes:
    """Render a simple PDF fallback with template-aware accent styling."""
    from app.services.accent_colors import accent_from_resume

    data = _clean_resume_for_pdf(resume_json)
    th = _default_pdf_theme(template_id)
    custom_hex = accent_from_resume(resume_json or {}, fallback=str(th.get("accent_hex") or "0e7490").lstrip("#"))
    th["accent_hex"] = f"#{custom_hex}" if not str(custom_hex).startswith("#") else custom_hex
    th["accent"] = colors.HexColor(th["accent_hex"])
    if (template_id or "").strip().lower() == "latex_ats_clean":
        return _build_clean_structured_pdf(data, th)
    name_style, head, body, small, bull, job_head, accent = _styles(th)
    profile = str(th.get("profile") or "ats")
    accent_hex = str(th.get("accent_hex") or "#0e7490")
    if not accent_hex.startswith("#"):
        accent_hex = f"#{accent_hex}"
    muted_hex = str(th.get("muted_hex") or "4b5563")

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
    section_titles = {
        "summary": "Executive Summary" if profile == "executive" else ("Profile Snapshot" if profile == "data" else "Summary"),
        "experience": "Professional Experience" if profile in {"executive", "web"} else "Experience",
        "education": "Education",
        "skills": "Core Skills" if profile in {"executive", "web"} else "Skills",
        "projects": "Projects",
    }

    story.append(Paragraph(_escape(c.get("name") or "Candidate"), name_style))

    if c.get("location"):
        story.append(Paragraph(_escape(_sanitize_display_text(c["location"])), small))
    contact_bits = [
        _escape(_sanitize_display_text(x))
        for x in (c.get("email"), c.get("phone"))
        if x and str(x).strip()
    ]
    if contact_bits:
        story.append(Paragraph(" | ".join(contact_bits), small))
    link_bits = []
    if c.get("linkedin"):
        link_bits.append(_escape(_short_url(c["linkedin"])))
    if c.get("github"):
        link_bits.append(_escape(_sanitize_display_text(c["github"])))
    if link_bits:
        story.append(Paragraph(" | ".join(link_bits), small))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=th["rule_pt"], color=accent, spaceAfter=12))

    def add_summary() -> None:
        if not data.get("summary"):
            return
        story.append(Paragraph(section_titles["summary"], head))
        story.append(Paragraph(_escape(data["summary"]), body))
        story.append(Spacer(1, 6))

    def add_experience() -> None:
        exps = data.get("experience") or []
        if not exps:
            return
        story.append(Paragraph(section_titles["experience"], head))
        for exp in exps:
            title = _escape(exp.get("title") or "")
            company = _escape(exp.get("company") or "")
            sd, ed = exp.get("start_date") or "", exp.get("end_date") or ""
            dates = ""
            if sd or ed:
                dates = f"{_escape(sd)} - {_escape(ed or 'Present')}"
            if title and company and company != "-":
                hdr = f"<b>{title}</b> &nbsp;<font color='{accent_hex}'>&bull;</font>&nbsp; <i>{company}</i>"
            elif title:
                hdr = f"<b>{title}</b>"
            elif company:
                hdr = f"<b>{company}</b>"
            else:
                hdr = "<b>Experience</b>"
            if dates:
                hdr += f' &nbsp;<font size="9" color="{muted_hex}">({dates})</font>'
            story.append(Paragraph(hdr, job_head))
            for item in exp.get("bullets") or []:
                story.append(Paragraph(f"&bull; {_escape(item)}", bull))
            story.append(Spacer(1, 4))

    def add_education() -> None:
        rows = data.get("education") or []
        if not rows:
            return
        story.append(Paragraph(section_titles["education"], head))
        for edu in rows:
            deg = _escape(edu.get("degree") or "")
            inst = _escape(edu.get("institution") or "")
            fld = _escape(edu.get("field") or "")
            yr = _escape(edu.get("year") or "")
            head_ln = f"<b>{deg}</b>" if deg else ""
            if inst:
                head_ln += (", " if head_ln else "") + f"<i>{inst}</i>"
            tail = " | ".join(filter(None, [fld, yr]))
            if tail:
                head_ln += f' <font color="{muted_hex}">({tail})</font>'
            story.append(Paragraph(head_ln or "-", body))

    def add_skills() -> None:
        tech = (data.get("skills") or {}).get("technical") or []
        if not tech:
            return
        story.append(Paragraph(section_titles["skills"], head))
        clean = [_sanitize_display_text(x) for x in tech if str(x).strip()]
        if profile in {"data", "robotics"} and len(clean) > 8:
            midpoint = (len(clean) + 1) // 2
            left = ", ".join(_escape(x) for x in clean[:midpoint])
            right = ", ".join(_escape(x) for x in clean[midpoint:])
            col_w = max(120, (inner_w - 12) / 2)
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
            story.append(tbl)
            return
        for line in _format_skills_lines(clean):
            story.append(Paragraph(line, body))

    def add_projects() -> None:
        projects = data.get("projects") or []
        if not projects:
            return
        story.append(Spacer(1, 4))
        story.append(Paragraph(section_titles["projects"], head))
        for idx, project in enumerate(projects):
            if idx:
                story.append(Spacer(1, 8))
            name = _escape(project.get("name") or "")
            description = _escape(project.get("description") or "")
            if name:
                story.append(Paragraph(f"<b>{name}</b>", job_head))
            if description:
                for chunk in description.split("\n"):
                    clean = _norm_ws(chunk)
                    if clean:
                        story.append(Paragraph(clean, body))

    renderers = {
        "summary": add_summary,
        "experience": add_experience,
        "education": add_education,
        "skills": add_skills,
        "projects": add_projects,
    }
    for section in th.get("section_order") or []:
        fn = renderers.get(str(section))
        if fn:
            fn()

    doc.build(story)
    return buf.getvalue()
