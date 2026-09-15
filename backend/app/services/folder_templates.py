from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.template_registry import folder_template_structure_path, get_template_descriptor


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


def _url_escape(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").replace("{", "").replace("}", "")


def _best_headline(resume_json: dict[str, Any]) -> str:
    exp = resume_json.get("experience") or []
    if exp and isinstance(exp[0], dict):
        title = str(exp[0].get("title") or "").strip()
        if title:
            return title
    summary = str(resume_json.get("summary") or "").strip()
    if summary:
        return summary.split(".")[0][:80]
    return "Professional Resume"


_DOCCLASS_MARKER_RE = re.compile(r"^\s*%\s*resumeiq:documentclass=([^|]+)\|(.+)\s*$", re.I)


def _structure_parts(template_id: str) -> tuple[str, str]:
    """Return (docclass_spec, structure_tex_without_docclass)."""
    path = folder_template_structure_path(template_id)
    default_doc = "[a4paper,12pt]{memoir}"
    if path and path.is_file():
        raw = path.read_text(encoding="utf-8", errors="replace")
        doc_spec = default_doc
        lines = raw.splitlines()
        if lines:
            marker = _DOCCLASS_MARKER_RE.match(lines[0])
            if marker:
                cls = marker.group(1).strip()
                opts = marker.group(2).strip()
                if cls:
                    doc_spec = f"[{opts}]{{{cls}}}" if opts else f"{{{cls}}}"
                raw = "\n".join(lines[1:])

        begin_match = re.search(r"\\begin\s*\{\s*document\s*\}", raw, re.I)
        structure = raw[: begin_match.start()] if begin_match else raw
        structure = re.sub(r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}", "", structure, count=1, flags=re.I).strip()
        return doc_spec, structure

    return default_doc, r"""
\usepackage{XCharter}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[top=1cm,left=1cm,right=1cm,bottom=1cm]{geometry}
\usepackage{flowfram}
\usepackage{url}
\usepackage[usenames,dvipsnames]{xcolor}
\usepackage{tikz}
\usepackage{enumitem}
\setlist{noitemsep,nolistsep}
\setlength{\columnsep}{\baselineskip}
\newflowframe{0.2\textwidth}{\textheight}{0pt}{0pt}[left]
\newlength{\LeftMainSep}
\setlength{\LeftMainSep}{0.2\textwidth}
\addtolength{\LeftMainSep}{1\columnsep}
\newstaticframe{1.5pt}{\textheight}{\LeftMainSep}{0pt}
\begin{staticcontents}{1}
\hfill
\tikz{\draw[loosely dotted,color=RoyalBlue,line width=1.5pt,yshift=0](0,0) -- (0,\textheight);}
\hfill\mbox{}
\end{staticcontents}
\addtolength{\LeftMainSep}{1.5pt}
\addtolength{\LeftMainSep}{1\columnsep}
\newflowframe{0.7\textwidth}{\textheight}{\LeftMainSep}{0pt}[main01]
\pagestyle{empty}
\setlength{\parindent}{0pt}
\newcommand{\userinformation}[1]{\renewcommand{\userinformation}{#1}}
\newcommand{\cvheading}[1]{{\Huge\bfseries\color{RoyalBlue} #1} \par\vspace{.6\baselineskip}}
\newcommand{\cvsubheading}[1]{{\Large\bfseries #1} \bigbreak}
\newcommand{\Sep}{\vspace{1em}}
\newcommand{\SmallSep}{\vspace{0.5em}}
\newcommand{\aboutme}[2]{\textbf{\color{RoyalBlue} #1}~~#2\par\Sep}
\newcommand{\CVSection}[1]{{\Large\textbf{#1}}\par\SmallSep}
\newcommand{\CVItem}[2]{\textbf{\color{RoyalBlue} #1}\par#2\SmallSep}
\newcommand{\bluebullet}{\textcolor{RoyalBlue}{$\circ$}~~}
""".strip()


def _itemize(lines: list[str]) -> str:
    clean = [str(line).strip() for line in lines if str(line).strip()]
    if not clean:
        return "See full resume for details."
    body = "\n".join(f"\\item {_tex_escape(line)}" for line in clean)
    return "\\begin{itemize}\n" + body + "\n\\end{itemize}"


def _education_section(resume_json: dict[str, Any]) -> str:
    items: list[str] = []
    for row in (resume_json.get("education") or [])[:5]:
        if not isinstance(row, dict):
            continue
        degree = _tex_escape(row.get("degree") or "")
        field = _tex_escape(row.get("field") or "")
        school = _tex_escape(row.get("institution") or "")
        year = _tex_escape(row.get("year") or "")
        label = ", ".join(part for part in (year, school) if part)
        detail = degree or field or "Education"
        if degree and field and field.lower() not in degree.lower():
            detail = f"{degree} in {field}"
        items.append(f"\\CVItem{{{label or 'Education'}}}{{{detail}}}")
    if not items:
        items.append("\\CVItem{Education}{Add your academic background in the resume editor.}")
    return "\n".join(items)


def _experience_section(resume_json: dict[str, Any]) -> str:
    items: list[str] = []
    for row in (resume_json.get("experience") or [])[:6]:
        if not isinstance(row, dict):
            continue
        title = _tex_escape(row.get("title") or "")
        company = _tex_escape(row.get("company") or "")
        start = _tex_escape(row.get("start_date") or "")
        end = _tex_escape(row.get("end_date") or "")
        label_parts = [part for part in (start, end) if part]
        label = " -- ".join(label_parts) if label_parts else (company or title or "Experience")
        heading_parts = [part for part in (title, company) if part and part != "-"]
        body_head = " | ".join(heading_parts) if heading_parts else "Experience"
        bullets = row.get("bullets") or row.get("description") or []
        bullet_list = bullets if isinstance(bullets, list) else [bullets]
        body = body_head + "\n" + _itemize([str(x) for x in bullet_list][:8])
        items.append(f"\\CVItem{{{label}}}{{{body}}}")
    if not items:
        items.append("\\CVItem{Experience}{Add your work history in the resume editor.}")
    return "\n".join(items)


def _projects_section(resume_json: dict[str, Any]) -> str:
    items: list[str] = []
    for row in (resume_json.get("projects") or [])[:5]:
        if not isinstance(row, dict):
            continue
        name = _tex_escape(row.get("name") or "Project")
        stack = ", ".join(_tex_escape(x) for x in (row.get("tech_stack") or [])[:6] if str(x).strip())
        description = _tex_escape(row.get("description") or "")
        body = description or "Project summary"
        if stack:
            body = f"\\textit{{{stack}}}\\\\ {body}"
        items.append(f"\\CVItem{{{name}}}{{{body}}}")
    if not items:
        return ""
    return "\\CVSection{Projects}\n\n" + "\n".join(items) + "\n\\Sep\n"


def _skills_section(resume_json: dict[str, Any]) -> str:
    skills = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (skills.get("tools") or []) if str(x).strip()]
    certs = [str(x).strip() for x in (skills.get("certifications") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))
    left = merged[: max(1, (len(merged) + 1) // 2)]
    right = merged[max(1, (len(merged) + 1) // 2) :]
    if not merged:
        skill_grid = "Add your skills in the resume editor."
    else:
        rows = max(len(left), len(right))
        table_rows: list[str] = []
        for idx in range(rows):
            a = f"\\bluebullet {_tex_escape(left[idx])}" if idx < len(left) else ""
            b = f"\\bluebullet {_tex_escape(right[idx])}" if idx < len(right) else ""
            table_rows.append(f"{a} & {b}\\\\")
        skill_grid = (
            "\\begin{tabular}{p{0.28\\textwidth} p{0.28\\textwidth}}\n"
            + "\n".join(table_rows)
            + "\n\\end{tabular}"
        )
    parts = [f"\\CVItem{{Core skills}}{{{skill_grid}}}"]
    if certs:
        parts.append(f"\\CVItem{{Certifications}}{{{_tex_escape(', '.join(certs[:8]))}}}")
    return "\n".join(parts)


def _web_contact_lines(resume_json: dict[str, Any]) -> str:
    contact = resume_json.get("contact") or {}
    location = _tex_escape(contact.get("location") or "")
    phone = _tex_escape(contact.get("phone") or "")
    email = _tex_escape(contact.get("email") or "")
    linkedin = _tex_escape(contact.get("linkedin") or "")
    github = _tex_escape(contact.get("github") or "")
    lines: list[str] = []
    for item in (location, phone, email, linkedin, github):
        if item:
            lines.append(item)
    return " \\\\\n".join(lines)


def _web_experience_block(resume_json: dict[str, Any]) -> str:
    chunks: list[str] = []
    for row in (resume_json.get("experience") or [])[:6]:
        if not isinstance(row, dict):
            continue
        title = _tex_escape(row.get("title") or "Role")
        company = _tex_escape(row.get("company") or "")
        sd = _tex_escape(row.get("start_date") or "")
        ed = _tex_escape(row.get("end_date") or "Present")
        span = f"{sd} - {ed}".strip(" -")
        bullets = row.get("bullets") or row.get("description") or []
        if not isinstance(bullets, list):
            bullets = [bullets]
        bullet_lines = [str(item).strip() for item in bullets if str(item).strip()][:8]
        heading = f"{company} - {title}" if company else title
        items = "\n".join(f"    \\item {_tex_escape(line)}" for line in bullet_lines) or "    \\item Impact and responsibilities."
        chunks.append(
            "\n".join(
                [
                    f"\\textbf{{\\uppercase{{{_tex_escape(span or 'Experience')}}}}} \\\\",
                    f"\\textbf{{{heading}}}",
                    "\\begin{itemize}",
                    items,
                    "\\end{itemize}",
                    "",
                ]
            )
        )
    if not chunks:
        return "\\textit{Add experience in the resume editor.}\n"
    return "\n".join(chunks)


def _web_education_block(resume_json: dict[str, Any]) -> str:
    rows: list[str] = []
    for row in (resume_json.get("education") or [])[:4]:
        if not isinstance(row, dict):
            continue
        degree = _tex_escape(row.get("degree") or "")
        field = _tex_escape(row.get("field") or "")
        school = _tex_escape(row.get("institution") or "")
        year = _tex_escape(row.get("year") or "")
        if field and field.lower() not in degree.lower():
            degree = f"{degree} in {field}" if degree else field
        line = f"\\textbf{{\\uppercase{{{year or 'Education'}}}}} \\\\ \\textbf{{{school} - {degree or 'Program'}}} \\\\"
        rows.append(line)
    if not rows:
        return "\\textit{Add education in the resume editor.}\n"
    return "\n".join(rows)


def _web_skills_block(resume_json: dict[str, Any]) -> str:
    skills = resume_json.get("skills") or {}
    technical = [str(x).strip() for x in (skills.get("technical") or []) if str(x).strip()]
    languages = [str(x).strip() for x in (resume_json.get("languages") or []) if str(x).strip()]
    certs = [str(x).strip() for x in (skills.get("certifications") or []) if str(x).strip()]
    merged = technical[:14]
    if languages:
        merged.append("Languages: " + ", ".join(languages[:4]))
    if certs:
        merged.append("Certifications: " + ", ".join(certs[:4]))
    if not merged:
        merged = ["Add skills in the resume editor."]
    items = "\n".join(f"    \\item {_tex_escape(item)}" for item in merged)
    return "\\begin{itemize}\n" + items + "\n\\end{itemize}\n"


def _render_web_template_latex(
    template_id: str,
    resume_json: dict[str, Any],
    docclass_spec: str,
    structure_tex: str,
) -> str:
    contact = resume_json.get("contact") or {}
    name = _tex_escape(contact.get("name") or "Candidate Name")
    summary = _tex_escape(resume_json.get("summary") or "Add a professional summary in the resume editor.")
    contact_lines = _web_contact_lines(resume_json)
    experience = _web_experience_block(resume_json)
    education = _web_education_block(resume_json)
    skills = _web_skills_block(resume_json)
    desc = get_template_descriptor(template_id)
    title_name = _tex_escape(desc.name if desc else "Web LaTeX Template")
    from app.services.accent_colors import accent_from_resume, accent_rgb_tuple

    hex6 = accent_from_resume(resume_json, fallback="eb5757")
    r, g, b = accent_rgb_tuple(hex6)
    accent_block = (
        f"\\providecolor{{coral}}{{RGB}}{{{r},{g},{b}}}\n"
        f"\\definecolor{{accent}}{{HTML}}{{{hex6}}}\n"
    )

    return (
        "\\documentclass"
        + docclass_spec
        + "\n\n"
        + structure_tex
        + "\n\n"
        + "\\providecommand{\\headingfont}{}\n"
        + accent_block
        + "\n\\begin{document}\n\n"
        + "{\\headingfont\\color{accent} \\Huge \\textbf{Hello}}\\\\[-0.2em]\n"
        + "{\\headingfont\\LARGE \\textbf{I'm "
        + name
        + "}}\\\\[1em]\n"
        + (contact_lines + " \\\\[1em]\n" if contact_lines else "")
        + "\\section*{Professional Summary}\n"
        + summary
        + "\n\n"
        + "\\section*{Professional Experience}\n\n"
        + experience
        + "\n"
        + "\\section*{Education}\n"
        + education
        + "\n\n"
        + "\\section*{Skills}\n"
        + skills
        + "\n\\vfill\n\\small Imported template style: "
        + title_name
        + "\n"
        + "\\end{document}\n"
    )


def render_folder_template_latex(template_id: str, resume_json: dict[str, Any]) -> str:
    desc = get_template_descriptor(template_id)
    if desc and desc.source == "zip" and desc.entry_path:
        from app.services.packaged_templates import render_zip_packaged_latex

        return render_zip_packaged_latex(desc.entry_path, resume_json)

    docclass_spec, structure_tex = _structure_parts(template_id)
    if desc and desc.source == "web":
        return _render_web_template_latex(template_id, resume_json, docclass_spec, structure_tex)

    contact = resume_json.get("contact") or {}
    name = _tex_escape(contact.get("name") or "Candidate Name")
    email = _url_escape(contact.get("email") or "")
    linkedin = _url_escape(contact.get("linkedin") or "")
    github = _url_escape(contact.get("github") or "")
    phone = _tex_escape(contact.get("phone") or "")
    location = _tex_escape(contact.get("location") or "")
    summary = _tex_escape(resume_json.get("summary") or "Add a summary in the Resume AI editor.")
    headline = _tex_escape(_best_headline(resume_json))

    sidebar_lines = [
        r"\begin{flushright}",
        r"\small",
        f"{name} \\\\",
    ]
    if email:
        sidebar_lines.append(f"\\url{{{email}}} \\\\")
    if linkedin:
        sidebar_lines.append(f"\\url{{{linkedin}}} \\\\")
    if github:
        sidebar_lines.append(f"\\url{{{github}}} \\\\")
    if phone:
        sidebar_lines.append(f"{phone} \\\\")
    if location:
        sidebar_lines.extend([r"\Sep", r"\textbf{Location} \\", f"{location} \\\\"])
    sidebar_lines.extend([r"\vfill", r"\end{flushright}"])
    sidebar = "\n".join(sidebar_lines)

    projects = _projects_section(resume_json)

    return (
        "\\documentclass"
        + docclass_spec
        + "\n\n"
        + structure_tex
        + "\n\n"
        + "\\userinformation{\n"
        + sidebar
        + "\n}\n\n"
        + "\\begin{document}\n\n"
        + "\\userinformation\n\n"
        + "\\framebreak\n\n"
        + f"\\cvheading{{{name}}}\n\n"
        + f"\\cvsubheading{{{headline}}}\n\n"
        + f"\\aboutme{{About Me}}{{{summary}}}\n\n"
        + "\\CVSection{Education}\n\n"
        + _education_section(resume_json)
        + "\n\\Sep\n\n"
        + "\\CVSection{Experience}\n\n"
        + _experience_section(resume_json)
        + "\n\\Sep\n\n"
        + projects
        + "\\CVSection{Skills}\n\n"
        + _skills_section(resume_json)
        + "\n\\Sep\n\n"
        + "\\end{document}\n"
    )
