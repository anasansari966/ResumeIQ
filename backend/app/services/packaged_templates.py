"""Discover LaTeX resume templates shipped as .zip files under backend/templates/."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

# app/services/*.py -> parent.parent.parent == backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ZIP_DIR = _BACKEND_ROOT / "templates"
_EXTRACT_ROOT = _ZIP_DIR / ".extracted"


def packaged_zip_templates_dir() -> Path:
    return _ZIP_DIR


def slug_from_zip(zip_path: Path) -> str:
    stem = zip_path.stem.lower()
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "template"


def display_name_from_zip(zip_path: Path) -> str:
    s = zip_path.stem
    s = re.sub(r"\s*\(\d+\)\s*$", "", s)
    tokens = re.split(r"[-_\s]+", s.lower())
    skip = {"latex", "resume", "template", "free", "download", "a", "an", "the", "and", "or"}
    kept = [t for t in tokens if t and t not in skip and not t.isdigit()]
    if not kept:
        return s.replace("-", " ").strip().title() or zip_path.stem
    return " ".join(w.capitalize() for w in kept)


def ensure_zip_extracted(zip_path: Path) -> Path:
    slug = slug_from_zip(zip_path)
    dest = _EXTRACT_ROOT / slug
    marker = dest / ".resumeiq_extracted"
    reuse = False
    if dest.is_dir() and marker.is_file():
        try:
            reuse = float(marker.read_text(encoding="utf-8").strip()) >= zip_path.stat().st_mtime
        except (ValueError, OSError):
            reuse = False
    if not reuse:
        dest.mkdir(parents=True, exist_ok=True)
        for p in dest.iterdir():
            if p.name == ".resumeiq_extracted":
                continue
            if p.is_file():
                p.unlink()
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                if member.startswith("__MACOSX") or member.endswith("/"):
                    continue
                base = Path(member).name
                if not base.lower().endswith(".tex") or base.startswith("."):
                    continue
                (dest / base).write_bytes(zf.read(member))
        marker.write_text(str(zip_path.stat().st_mtime), encoding="utf-8")
    return dest


def main_tex_in_folder(folder: Path) -> Path | None:
    tex = sorted(folder.glob("*.tex"))
    return tex[0] if tex else None


def _tex_escape(value: Any) -> str:
    text = str(value or "").strip()
    return (
        text.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("~", "\\textasciitilde{}")
        .replace("^", "\\textasciicircum{}")
    )


def _contact_line(resume_json: dict[str, Any]) -> str:
    c = resume_json.get("contact") or {}
    parts: list[str] = []
    for key in ("location", "email", "phone"):
        v = _tex_escape(c.get(key) or "")
        if v:
            parts.append(v)
    for key in ("linkedin", "github"):
        v = str(c.get(key) or "").strip()
        if v:
            parts.append(_tex_escape(v))
    return " --- ".join(parts) if parts else _tex_escape("Add contact details in the editor.")


def _norm_doc(tex: str) -> str:
    i = tex.lower().find(r"\begin{document}")
    return tex[i:].lower() if i >= 0 else tex.lower()


def detect_zip_body_layout(full_tex: str) -> str:
    """Match each packaged .tex family so PDF export mirrors its LaTeX structure."""
    doc = _norm_doc(full_tex)
    if r"\name{" in full_tex and r"\contact{" in full_tex and r"\role{" in full_tex:
        return "chicago"
    if r"\section*{summary}" in doc and r"\header{" in full_tex:
        return "easy"
    if "multicols" in doc and r"\section*{professional experience}" in doc:
        return "classic"
    if r"\subsection{" in doc and r"\section{professional experience}" in doc:
        return "milano"
    return "generic"


def _exp_bullets(row: dict[str, Any], limit: int = 10) -> list[str]:
    bullets = row.get("bullets") or row.get("description") or []
    if not isinstance(bullets, list):
        bullets = [bullets]
    return [str(b).strip() for b in bullets if str(b).strip()][:limit]


def _body_chicago(resume_json: dict[str, Any]) -> str:
    c = resume_json.get("contact") or {}
    name = _tex_escape(c.get("name") or "Your Name")
    loc = _tex_escape(c.get("location") or "")
    phone = _tex_escape(c.get("phone") or "")
    email = _tex_escape(c.get("email") or "")
    li = str(c.get("linkedin") or "").strip()
    gh = str(c.get("github") or "").strip()
    if li or gh:
        extra = " | ".join(_tex_escape(x) for x in (li, gh) if x)
        loc = f"{loc} | {extra}" if loc else extra
    summary = _tex_escape(resume_json.get("summary") or "Add a professional summary in the resume editor.")
    lines: list[str] = [
        rf"\name{{{name}}}",
        r"\vspace{-0.5em}",
        rf"\contact{{{loc}}}{{{phone}}}{{{email}}}",
        r"\vspace{-0.5em}",
        r"\begin{center}",
        rf"\textit{{{summary}}}",
        r"\end{center}",
        "",
        r"\section{PROFESSIONAL EXPERIENCE}",
        "",
        r"\vspace{1em}",
    ]
    exp = resume_json.get("experience") or []
    first = True
    wrote = False
    for row in exp[:8]:
        if not isinstance(row, dict):
            continue
        title = _tex_escape(row.get("title") or "Role")
        company = _tex_escape(row.get("company") or "Company")
        where = _tex_escape(str(row.get("location") or "").strip() or (c.get("location") or ""))
        sd = _tex_escape(row.get("start_date") or "")
        ed = _tex_escape(row.get("end_date") or "Present")
        span = f"{sd}--{ed}" if sd or ed else ed
        lines.append(rf"\role{{{company}}}{{{where}}}{{{title}}}{{{span}}}")
        opts = "[leftmargin=*,nosep]" if first else "[leftmargin=*,nosep,topsep=0pt]"
        first = False
        bl = _exp_bullets(row)
        lines.append(rf"\begin{{itemize}}{opts}")
        if bl:
            for b in bl:
                lines.append("  \\item " + _tex_escape(b))
        else:
            lines.append(r"  \item \textit{Add role highlights in the resume editor.}")
        lines.append(r"\end{itemize}")
        lines.append("")
        wrote = True
    if not wrote:
        lines.append(r"\textit{Add experience in the resume editor.}")
        lines.append("")

    lines.extend([r"\vspace{1em}", r"\section{EDUCATION}", "", r"\vspace{0.5em}"])
    edu = resume_json.get("education") or []
    edu_w = False
    for row in edu[:5]:
        if not isinstance(row, dict):
            continue
        school = _tex_escape(row.get("institution") or "School")
        city = _tex_escape(str(row.get("location") or "").strip() or "")
        deg = _tex_escape(row.get("degree") or "Degree")
        yr = _tex_escape(row.get("year") or "")
        lines.append(rf"\role{{{school}}}{{{city}}}{{{deg}}}{{{yr}}}")
        lines.append("")
        edu_w = True
    if not edu_w:
        lines.append(r"\textit{Add education in the resume editor.}")
        lines.append("")

    skills = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (skills.get("tools") or []) if str(x).strip()]
    langs = [str(x).strip() for x in (resume_json.get("languages") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:16]
    if langs:
        merged.append("Languages: " + ", ".join(langs[:5]))
    certs = [str(x).strip() for x in (skills.get("certifications") or []) if str(x).strip()]
    if certs:
        merged.append("Certifications: " + ", ".join(certs[:6]))
    lines.extend([r"\vspace{1em}", r"\section{SKILLS}", "", r"\vspace{0.5em}"])
    if merged:
        lines.append(r"\begin{itemize}[leftmargin=*,nosep]")
        for x in merged[:18]:
            lines.append("  \\item " + _tex_escape(x))
        lines.append(r"\end{itemize}")
    else:
        lines.append(r"\begin{itemize}[leftmargin=*,nosep]")
        lines.append(r"  \item \textit{Add skills in the resume editor.}")
        lines.append(r"\end{itemize}")
    return "\n".join(lines)


def _body_milano(resume_json: dict[str, Any]) -> str:
    c = resume_json.get("contact") or {}
    name = _tex_escape(c.get("name") or "Your Name")
    loc = _tex_escape(c.get("location") or "")
    em = _tex_escape(c.get("email") or "")
    ph = _tex_escape(c.get("phone") or "")
    line2 = " | ".join(x for x in (loc, em, ph) if x) or _tex_escape("Add contact details.")
    summary = _tex_escape(resume_json.get("summary") or "Add a professional summary in the resume editor.")
    lines: list[str] = [
        r"% Header",
        r"{\huge\bfseries\color{headingcolor} " + name + "}",
        "",
        r"{\small",
        line2,
        "}",
        "",
        r"\noindent{\color{headingcolor}\rule{\linewidth}{0.4pt}}",
        "",
        r"{\small " + summary + "}",
        "",
        r"\section{Professional Experience}",
        "",
    ]
    exp = resume_json.get("experience") or []
    wrote = False
    for row in exp[:8]:
        if not isinstance(row, dict):
            continue
        title = _tex_escape(row.get("title") or "Role")
        company = _tex_escape(row.get("company") or "Company")
        locj = _tex_escape(str(row.get("location") or "").strip() or (c.get("location") or ""))
        sd = _tex_escape(row.get("start_date") or "")
        ed = _tex_escape(row.get("end_date") or "Present")
        span = f"{sd}--{ed}" if sd or ed else ed
        block = f"{company}, {locj}" if locj else company
        lines.extend(
            [
                rf"\subsection{{{title}}}",
                r"\vspace{-0.5em}",
                rf"\textbf{{{block}}}\\",
                span,
                r"\vspace{-0.5em}",
                r"\begin{itemize}",
            ]
        )
        bl = _exp_bullets(row)
        if bl:
            for b in bl:
                lines.append("    \\item " + _tex_escape(b))
        else:
            lines.append(r"    \item \textit{Add role highlights in the resume editor.}")
        lines.append(r"\end{itemize}")
        lines.append("")
        wrote = True
    if not wrote:
        lines.append(r"\textit{Add experience in the resume editor.}")
        lines.append("")

    lines.extend([r"\section{Education}", ""])
    edu = resume_json.get("education") or []
    if edu:
        for row in edu[:4]:
            if not isinstance(row, dict):
                continue
            school = _tex_escape(row.get("institution") or "")
            city = _tex_escape(str(row.get("location") or "").strip() or "")
            yr = _tex_escape(row.get("year") or "")
            deg = _tex_escape(row.get("degree") or "")
            field = _tex_escape(row.get("field") or "")
            head = f"{school}, {city}" if city else school
            lines.append(rf"\textbf{{{head}}}\\")
            if yr:
                lines.append(yr + r"\\")
            degline = deg + (f" ({field})" if field and field.lower() not in deg.lower() else "")
            if degline:
                lines.append(degline + r"\\")
            lines.append("")
    else:
        lines.append(r"\textit{Add education in the resume editor.}")
        lines.append("")

    skills = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (skills.get("tools") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:14]
    lines.extend([r"\section{Additional Skills}", "", r"\begin{itemize}"])
    if merged:
        lines.append("    \\item " + _tex_escape(", ".join(merged)))
    langs = [str(x).strip() for x in (resume_json.get("languages") or []) if str(x).strip()]
    if langs:
        lines.append("    \\item " + _tex_escape("Languages: " + ", ".join(langs[:5])))
    if not merged and not langs:
        lines.append(r"    \item \textit{Add skills in the resume editor.}")
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def _body_easy(resume_json: dict[str, Any]) -> str:
    c = resume_json.get("contact") or {}
    name = _tex_escape(c.get("name") or "Your Name")
    loc = _tex_escape(c.get("location") or "")
    em = _tex_escape(c.get("email") or "")
    ph = _tex_escape(c.get("phone") or "")
    head_line = " | ".join(x for x in (loc, em, ph) if x) or _tex_escape("Add contact details.")
    summary = _tex_escape(resume_json.get("summary") or "Add a professional summary in the resume editor.")
    lines: list[str] = [
        r"% Header",
        r"\begin{center}",
        r"{\fontsize{24}{28}\selectfont\bfseries\color{headercolor} " + name + r"}\\[0.5em]",
        head_line,
        r"\end{center}",
        r"\noindent\rule{\textwidth}{2pt}",
        r"\section*{Summary}",
        summary,
        r"\section*{Professional Experience}",
        r"\vspace{0.3em}",
    ]
    exp = resume_json.get("experience") or []
    wrote = False
    for row in exp[:8]:
        if not isinstance(row, dict):
            continue
        title = _tex_escape(row.get("title") or "Role")
        company = _tex_escape(row.get("company") or "Company")
        locj = _tex_escape(str(row.get("location") or "").strip() or (c.get("location") or ""))
        sd = _tex_escape(row.get("start_date") or "")
        ed = _tex_escape(row.get("end_date") or "Present")
        span = f"{sd} -- {ed}".strip(" -") if sd or ed else ed
        lines.append(rf"\header{{{title}}} \hfill \hfill \textit {{{span}}}\\")
        block = f"{company}, {locj}" if locj else company
        lines.append(block)
        lines.append(r"\begin{itemize}[leftmargin=2em,itemsep=0.3ex]")
        bl = _exp_bullets(row)
        if bl:
            for b in bl:
                lines.append("  \\item " + _tex_escape(b))
        else:
            lines.append(r"  \item \textit{Add role highlights in the resume editor.}")
        lines.append(r"\end{itemize}")
        lines.append(r"\vspace{0.4em}")
        wrote = True
    if not wrote:
        lines.append(r"\textit{Add experience in the resume editor.}")
        lines.append(r"\vspace{0.3em}")

    lines.extend([r"\section*{Education}", ""])
    edu = resume_json.get("education") or []
    if edu:
        for row in edu[:4]:
            if not isinstance(row, dict):
                continue
            deg = _tex_escape(row.get("degree") or "Degree")
            yr = _tex_escape(row.get("year") or "")
            school = _tex_escape(row.get("institution") or "")
            city = _tex_escape(str(row.get("location") or "").strip() or "")
            lines.append(rf"\header{{{deg}}} \hfill \textit {{{yr}}}\\")
            honors = _tex_escape(str(row.get("honors") or row.get("gpa") or "").strip())
            if honors:
                lines.append(honors + r"\\")
            tail = f"{school}, {city}" if city else school
            if tail:
                lines.append(tail)
            lines.append(r"\vspace{0.3em}")
    else:
        lines.append(r"\textit{Add education in the resume editor.}")
        lines.append(r"\vspace{0.3em}")

    skills = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (skills.get("tools") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:20]
    lines.extend([r"\section*{Additional Skills}", r"\begin{itemize}[leftmargin=2em,itemsep=0.3ex]"])
    if merged:
        chunk = ", ".join(_tex_escape(x) for x in merged)
        lines.append(f"  \\item {chunk}")
    langs = [str(x).strip() for x in (resume_json.get("languages") or []) if str(x).strip()]
    if langs:
        lines.append("  \\item " + _tex_escape("Languages: " + ", ".join(langs[:5])))
    if not merged and not langs:
        lines.append(r"  \item \textit{Add skills in the resume editor.}")
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def _body_classic(resume_json: dict[str, Any]) -> str:
    c = resume_json.get("contact") or {}
    name = _tex_escape(c.get("name") or "Your Name")
    loc = _tex_escape(c.get("location") or "")
    em = _tex_escape(c.get("email") or "")
    ph = _tex_escape(c.get("phone") or "")
    head = " | ".join(x for x in (loc, em, ph) if x) or _tex_escape("Add contact details.")
    summary = _tex_escape(resume_json.get("summary") or "Add a professional summary in the resume editor.")
    lines: list[str] = [
        r"\begin{flushleft}",
        r"    \textbf{\LARGE\color{sectioncolor} " + name + r"} \\[0.5ex]",
        r"    \color{black}\rule{\linewidth}{0.5pt} \\[0.5ex]",
        "    " + head,
        r"\end{flushleft}",
        "",
        r"\section*{SUMMARY}",
        r"\vspace{0.5em}",
        summary,
        "",
        r"\vspace{1em}",
        r"\section*{PROFESSIONAL EXPERIENCE}",
        r"\vspace{0.5em}",
    ]
    exp = resume_json.get("experience") or []
    wrote = False
    for row in exp[:8]:
        if not isinstance(row, dict):
            continue
        company = _tex_escape(row.get("company") or "Company")
        title = _tex_escape(row.get("title") or "Role")
        locj = _tex_escape(str(row.get("location") or "").strip() or (c.get("location") or ""))
        sd = _tex_escape(row.get("start_date") or "")
        ed = _tex_escape(row.get("end_date") or "Present")
        span = f"{sd} -- {ed}".strip(" -") if sd or ed else ed
        left = f"{company}, {locj} \\\\\n{title}" if locj else f"{company} \\\\\n{title}"
        lines.extend(
            [
                r"\begin{minipage}[t]{0.75\textwidth}",
                left,
                r"\end{minipage}",
                r"\hfill ",
                r"\begin{minipage}[t]{0.2\textwidth}",
                rf"\hfill \textit{{{span}}} ",
                r"\end{minipage}",
                "",
                r"\begin{multicols}{2}",
                r"\begin{itemize}[leftmargin=1em,noitemsep,topsep=0pt]",
            ]
        )
        bl = _exp_bullets(row, 12)
        if bl:
            for b in bl:
                lines.append("    \\item " + _tex_escape(b))
        else:
            lines.append(r"    \item \textit{Add role highlights in the resume editor.}")
        lines.extend([r"\end{itemize}", r"\end{multicols}", "", r"\vspace{1ex}", ""])
        wrote = True
    if not wrote:
        lines.append(r"\textit{Add experience in the resume editor.}")
        lines.append("")

    lines.extend([r"\vspace{1em}", r"\section*{EDUCATION}", r"\vspace{0.5em}"])
    edu = resume_json.get("education") or []
    if edu:
        for row in edu[:4]:
            if not isinstance(row, dict):
                continue
            school = _tex_escape(row.get("institution") or "")
            city = _tex_escape(str(row.get("location") or "").strip() or "")
            yr = _tex_escape(row.get("year") or "")
            deg = _tex_escape(row.get("degree") or "")
            field = _tex_escape(row.get("field") or "")
            head = f"{school}, {city}" if city else school
            degline = deg + (f" ({field})" if field and field.lower() not in deg.lower() else "")
            lines.append(rf"{head} \hfill \textit{{{yr}}} \\")
            if degline:
                lines.append(degline + r" \\")
            lines.append("")
    else:
        lines.append(r"\textit{Add education in the resume editor.}")
        lines.append("")

    skills = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (skills.get("tools") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:16]
    lines.extend([r"\vspace{1.5em}", r"\section*{ADDITIONAL SKILLS}", "", r"\begin{multicols}{2}", r"\begin{itemize}[noitemsep,topsep=0pt]"])
    if merged:
        half = max(1, (len(merged) + 1) // 2)
        lines.append("    \\item " + _tex_escape(", ".join(merged[:half])))
        if len(merged) > half:
            lines.append("    \\item " + _tex_escape(", ".join(merged[half:])))
    langs = [str(x).strip() for x in (resume_json.get("languages") or []) if str(x).strip()]
    if langs and not merged:
        lines.append("    \\item " + _tex_escape("Languages: " + ", ".join(langs[:5])))
    if not merged and not langs:
        lines.append(r"    \item \textit{Add skills in the resume editor.}")
    lines.extend([r"\end{itemize}", r"\end{multicols}"])
    return "\n".join(lines)


def _body_generic(resume_json: dict[str, Any]) -> str:
    """Fallback article layout when the .tex family is unknown."""
    c = resume_json.get("contact") or {}
    name = _tex_escape(c.get("name") or "Your Name")
    summary = _tex_escape(resume_json.get("summary") or "Add a professional summary in the resume editor.")
    lines: list[str] = [
        r"\begin{center}",
        r"{\Large\bfseries " + name + r"}\\[0.35em]",
        r"{\small " + _contact_line(resume_json) + r"}",
        r"\end{center}",
        r"\vspace{0.6em}",
        r"\section*{Professional Summary}",
        summary,
        r"\vspace{0.6em}",
        r"\section*{Professional Experience}",
        r"\vspace{0.3em}",
    ]
    exp = resume_json.get("experience") or []
    any_exp = False
    for row in exp[:8]:
        if not isinstance(row, dict):
            continue
        title = _tex_escape(row.get("title") or "")
        company = _tex_escape(row.get("company") or "")
        sd = _tex_escape(row.get("start_date") or "")
        ed = _tex_escape(row.get("end_date") or "Present")
        dates = f"{sd} -- {ed}".strip(" -") if sd or ed else ed
        bullet_lines = _exp_bullets(row)
        head_bits = [x for x in (company, title) if x]
        head = " --- ".join(head_bits) if head_bits else _tex_escape("Experience")
        line1 = r"\noindent\textbf{" + head + "}"
        if dates:
            line1 += r" \hfill \textit{" + dates + "}"
        lines.append(line1)
        lines.append(r"\vspace{0.2em}")
        if bullet_lines:
            lines.append(r"\begin{itemize}")
            for b in bullet_lines:
                lines.append(r"\item " + _tex_escape(b))
            lines.append(r"\end{itemize}")
        lines.append(r"\vspace{0.45em}")
        any_exp = True
    if not any_exp:
        lines.append(r"\textit{Add experience in the resume editor.}")
        lines.append(r"\vspace{0.5em}")

    lines.extend([r"\section*{Education}", r"\vspace{0.3em}"])
    edu = resume_json.get("education") or []
    edu_items: list[str] = []
    for row in edu[:6]:
        if not isinstance(row, dict):
            continue
        degree = _tex_escape(row.get("degree") or "")
        field = _tex_escape(row.get("field") or "")
        school = _tex_escape(row.get("institution") or "")
        year = _tex_escape(row.get("year") or "")
        bits = [x for x in (degree, field, school, year) if x]
        if bits:
            edu_items.append(" --- ".join(bits))
    if edu_items:
        lines.append(r"\begin{itemize}")
        for it in edu_items:
            lines.append(r"\item " + it)
        lines.append(r"\end{itemize}")
    else:
        lines.append(r"\textit{Add education in the resume editor.}")

    skills = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (skills.get("tools") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:28]
    lines.extend([r"\vspace{0.6em}", r"\section*{Skills}", r"\vspace{0.3em}"])
    if merged:
        lines.append(r"\begin{itemize}")
        for x in merged:
            lines.append(r"\item " + _tex_escape(x))
        lines.append(r"\end{itemize}")
    else:
        lines.append(r"\textit{Add skills in the resume editor.}")

    return "\n".join(lines)


def _body_from_resume(layout: str, resume_json: dict[str, Any]) -> str:
    if layout == "chicago":
        return _body_chicago(resume_json)
    if layout == "milano":
        return _body_milano(resume_json)
    if layout == "easy":
        return _body_easy(resume_json)
    if layout == "classic":
        return _body_classic(resume_json)
    return _body_generic(resume_json)


def render_zip_packaged_latex(entry_path: Path, resume_json: dict[str, Any]) -> str:
    from app.services.accent_colors import apply_accent_to_latex_preamble

    raw = entry_path.read_text(encoding="utf-8", errors="replace")
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    m_begin = re.search(r"\\begin\s*\{\s*document\s*\}", raw, re.I)
    m_end = None
    for cand in re.finditer(r"\\end\s*\{\s*document\s*\}", raw, re.I):
        m_end = cand
    if not m_begin or not m_end:
        raise ValueError(f"No document environment in {entry_path.name}")
    preamble = apply_accent_to_latex_preamble(raw[: m_begin.start()].rstrip(), resume_json)
    layout = detect_zip_body_layout(raw)
    body = _body_from_resume(layout, resume_json)
    return preamble + "\n\n\\begin{document}\n\n" + body + "\n\n\\end{document}\n"


def iter_packaged_template_paths() -> list[Path]:
    d = _ZIP_DIR
    if not d.is_dir():
        return []
    return sorted(d.glob("*.zip"))


