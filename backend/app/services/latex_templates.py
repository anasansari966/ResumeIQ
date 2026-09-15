from __future__ import annotations

import re
from typing import Any


LATEX_TEMPLATE_1 = "latex_template_1"
LATEX_TEMPLATE_2 = "latex_template_2"
LATEX_TEMPLATE_ROBOTICS = "latex_robotics_researcher"
LATEX_TEMPLATE_ATS = "latex_ats_clean"
LATEX_TEMPLATE_EXECUTIVE = "latex_executive_navy"
LATEX_TEMPLATE_SLATE = "latex_slate_minimal"
LATEX_TEMPLATE_DATA = "latex_data_compact"
LATEX_TEMPLATE_EMERALD = "latex_modern_emerald"


def list_latex_templates() -> list[tuple[str, str]]:
    return [
        (LATEX_TEMPLATE_ATS, "ATS-optimized (clean, simple layout)"),
        (LATEX_TEMPLATE_EXECUTIVE, "Executive navy (single-column, leadership tone)"),
        (LATEX_TEMPLATE_EMERALD, "Modern emerald (balanced and polished)"),
        (LATEX_TEMPLATE_DATA, "Data compact (high-density sections)"),
        (LATEX_TEMPLATE_SLATE, "Slate minimal (neutral and ATS-safe)"),
        (LATEX_TEMPLATE_ROBOTICS, "Robotics & research (blue / cyan)"),
        (LATEX_TEMPLATE_1, "MaltaCV (Template 1)"),
        (LATEX_TEMPLATE_2, "Puneet Resume (Template 2)"),
    ]


def is_latex_template_id(template_id: str) -> bool:
    return template_id in {
        LATEX_TEMPLATE_1,
        LATEX_TEMPLATE_2,
        LATEX_TEMPLATE_ROBOTICS,
        LATEX_TEMPLATE_ATS,
        LATEX_TEMPLATE_EXECUTIVE,
        LATEX_TEMPLATE_SLATE,
        LATEX_TEMPLATE_DATA,
        LATEX_TEMPLATE_EMERALD,
    }


def first_latex_template_id() -> str:
    return LATEX_TEMPLATE_ATS


def _norm_line(s: str) -> str:
    t = (s or "").replace("\u200b", "")
    t = re.sub(r"[\r\n]+", " ", t)
    return re.sub(r" +", " ", t).strip()


def _esc(s: str) -> str:
    t = str(s or "")
    return (
        t.replace("\\", "\\textbackslash{}")
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


def _resume_fields(resume_json: dict[str, Any]) -> dict[str, Any]:
    c = resume_json.get("contact") or {}
    sk = resume_json.get("skills") or {}
    return {
        "name": _esc(c.get("name") or "Candidate Name"),
        "email": _esc(c.get("email") or "email@example.com"),
        "phone": _esc(c.get("phone") or ""),
        "linkedin": _esc(c.get("linkedin") or ""),
        "github": _esc(c.get("github") or ""),
        "location": _esc(c.get("location") or ""),
        "summary": _esc(resume_json.get("summary") or ""),
        "skills": [_esc(x) for x in (sk.get("technical") or [])[:14]],
        "education": resume_json.get("education") or [],
        "experience": resume_json.get("experience") or [],
        "projects": resume_json.get("projects") or [],
    }


def _resume_fields_robotics(resume_json: dict[str, Any]) -> dict[str, Any]:
    d = _resume_fields(resume_json)
    sk = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (sk.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (sk.get("tools") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:36]
    d["skills_merged"] = [_esc(x) for x in merged] if merged else d["skills"]
    d["publications"] = resume_json.get("publications") or []
    d["languages"] = [_esc(str(x).strip()) for x in (resume_json.get("languages") or []) if str(x).strip()]
    d["scholar"] = _esc(str(resume_json.get("scholar") or "").strip())
    d["nationality"] = _esc(str(resume_json.get("nationality") or "").strip())
    d["references"] = resume_json.get("references")
    return d


def _robotics_edu_block(e: dict[str, Any]) -> str:
    degree = _esc(str(e.get("degree") or "").strip())
    field = _esc(str(e.get("field") or "").strip())
    inst = _esc(str(e.get("institution") or "").strip())
    year = _esc(str(e.get("year") or "").strip())
    gpa = e.get("gpa")
    gpa_s = _esc(str(gpa).strip()) if gpa not in (None, "") else ""
    if field and field not in degree:
        deg_part = f"{degree} in {field}" if degree else field
    else:
        deg_part = degree or field or "Program"
    line1 = f"{year} — {deg_part}" if year else deg_part
    parts = [f"\\blueitem{{{line1}}} \\\\", f"\\textit{{{inst}}}" if inst else ""]
    body = "\n".join(p for p in parts if p)
    if gpa_s:
        body += f" \\\\\n\\textbf{{GPA:}} {gpa_s}"
    return body + "\n\\vspace{0.3em}\n"


def _robotics_exp_block(e: dict[str, Any]) -> str:
    title = _esc(str(e.get("title") or "").strip())
    company = _esc(str(e.get("company") or "").strip())
    sd = _esc(str(e.get("start_date") or "").strip())
    ed = _esc(str(e.get("end_date") or "").strip())
    span = f"{sd} — {ed}" if sd or ed else ""
    bullets = e.get("bullets") or []
    if not bullets and e.get("description"):
        desc = e.get("description")
        bullets = desc if isinstance(desc, list) else [str(desc)]
    bullets = [str(b).strip() for b in bullets if str(b).strip()][:10]
    head = f"\\blueitem{{{span}{': ' if span and title else ''}{title}}} \\\\"
    sub = f"\\textit{{{company}}}" if company else ""
    if not bullets:
        return head + sub + "\n\\vspace{0.3em}\n"
    items = "\n".join(f"    \\item {_esc(b)}" for b in bullets)
    return f"{head}\n{sub}\n\\begin{{itemize}}\n{items}\n\\end{{itemize}}\n\\vspace{{0.3em}}\n"


def _robotics_pub_block(pub: str) -> str:
    raw = str(pub or "").strip()
    if not raw:
        return ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return ""
    title = _esc(lines[0])
    tail = " \\\\ ".join(_esc(x) for x in lines[1:])
    if tail:
        return f"\\blueitem{{{title}}} \\\\ {tail}\n\\vspace{{0.2em}}\n"
    return f"\\blueitem{{{title}}}\n\\vspace{{0.2em}}\n"


def _robotics_proj_block(p: dict[str, Any]) -> str:
    name = _esc(str(p.get("name") or "Project").strip())
    desc = str(p.get("description") or "").strip()
    stack = ", ".join(_esc(str(t).strip()) for t in (p.get("tech_stack") or [])[:8] if str(t).strip())
    head = f"\\blueitem{{{name}}} \\\\"
    sub = f"\\textit{{{stack}}}" if stack else ""
    chunks: list[str] = []
    if desc:
        for chunk in desc.replace("•", "\n").split("\n"):
            c = chunk.strip()
            if c:
                chunks.append(c)
    if len(chunks) == 1 and len(chunks[0]) > 200:
        chunks = [chunks[0][:400]]
    if not chunks:
        return f"{head}\n{sub}\n\\vspace{{0.3em}}\n" if sub else f"{head}\n\\vspace{{0.3em}}\n"
    items = "\n".join(f"    \\item {_esc(c)}" for c in chunks[:8])
    mid = f"\n{sub}\n" if sub else "\n"
    return f"{head}{mid}\\begin{{itemize}}\n{items}\n\\end{{itemize}}\n\\vspace{{0.3em}}\n"


def _robotics_ref_minipage(ref: Any) -> str:
    if isinstance(ref, str):
        t = ref.strip()
        return f"    {_esc(t)}" if t else ""
    if not isinstance(ref, dict):
        return ""
    name = _esc(str(ref.get("name") or "").strip())
    role = _esc(str(ref.get("title") or ref.get("role") or "").strip())
    dept = _esc(str(ref.get("department") or ref.get("dept") or "").strip())
    inst = _esc(str(ref.get("institution") or ref.get("org") or "").strip())
    email = _esc(str(ref.get("email") or "").strip())
    lines = [x for x in (name, role, dept, inst, f"Email: {email}" if email else "") if x]
    return " \\\\\n".join(lines)


_ROBOTICS_PREAMBLE = r"""\documentclass[11pt,a4paper]{article}

\usepackage[left=0.8in,top=0.8in,right=0.8in,bottom=0.8in]{geometry}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[default]{sourcesanspro}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{parskip}

\definecolor{titleblue}{HTML}{00199e}
\definecolor{subtitleblue}{HTML}{2ec1e0}
\definecolor{darktext}{HTML}{222222}

\color{darktext}
\linespread{0.9}
\setlength{\parskip}{0.1em}

\titleformat{\section}{\Large\bfseries\color{titleblue}}{}{0em}{}
\titlespacing*{\section}{0pt}{0.7em}{0.15em}

\newcommand{\blueitem}[1]{\textcolor{subtitleblue}{\textbf{#1}}}

\setlist[itemize]{label=\textbullet, leftmargin=*, noitemsep, topsep=0pt, parsep=0pt}

\begin{document}
"""


def _render_template_robotics(resume_json: dict[str, Any]) -> str:
    d = _resume_fields_robotics(resume_json)
    head = [r"{\Huge \textbf{\textcolor{titleblue}{" + d["name"] + r"}}} \vspace{0.2em}"]
    if d["location"]:
        head.append(d["location"])
    if d["phone"]:
        head.append("Mobile: " + d["phone"])
    if d["email"]:
        head.append("Email: " + d["email"])
    if d["linkedin"]:
        head.append("LinkedIn: " + d["linkedin"])
    if d["github"]:
        head.append("GitHub: " + d["github"])
    if d["scholar"]:
        head.append("Scholar: " + d["scholar"])
    if d["nationality"]:
        head.append("Nationality: " + d["nationality"])
    header = " \\\\\n".join(head) + "\n\n\\vspace{0.4em}\n\n"

    profile = (
        r"\section*{Personal Profile}" + "\n"
        + (d["summary"] if d["summary"] else r"\textit{Add a short professional profile in the Enhance tab.}")
        + "\n\n"
    )

    edu_body = "".join(_robotics_edu_block(e) for e in d["education"][:5])
    if not edu_body:
        edu_body = r"\textit{Add education in the Enhance tab.}" + "\n"
    education = r"\section*{Education}" + "\n\n" + edu_body + "\n"

    exp_body = "".join(_robotics_exp_block(e) for e in d["experience"][:6])
    if not exp_body:
        exp_body = r"\textit{Add experience in the Enhance tab.}" + "\n"
    experience = r"\section*{Experience}" + "\n\n" + exp_body + "\n"

    pubs_raw = [str(p).strip() for p in d["publications"] if str(p).strip()][:12]
    if pubs_raw:
        pubs = r"\section*{Academic Publications}" + "\n\n" + "".join(_robotics_pub_block(p) for p in pubs_raw) + "\n"
    else:
        pubs = ""

    proj_body = "".join(_robotics_proj_block(p) for p in d["projects"][:6])
    if proj_body:
        projects = r"\section*{Projects/Research}" + "\n\n" + proj_body + "\n"
    else:
        projects = ""

    skill_line = ", ".join(d["skills_merged"]) if d["skills_merged"] else "Add skills in the Enhance tab."
    lang_line = ""
    if d["languages"]:
        lang_line = r"\\" + "\nLanguages: " + ", ".join(d["languages"])
    skills = r"\section*{Skills}" + "\n" + skill_line + lang_line + "\n\n"

    refs = d.get("references")
    ref_tex = ""
    if isinstance(refs, list) and len(refs) >= 2:
        a = _robotics_ref_minipage(refs[0])
        b = _robotics_ref_minipage(refs[1])
        if a and b:
            ref_tex = (
                r"\section*{References}" + "\n\n"
                r"\begin{minipage}[t]{0.48\textwidth}" + "\n"
                + a
                + "\n"
                r"\end{minipage}%" + "\n"
                r"\hfill" + "\n"
                r"\begin{minipage}[t]{0.48\textwidth}" + "\n"
                + b
                + "\n"
                r"\end{minipage}" + "\n\n"
            )
    if not ref_tex:
        ref_tex = r"\section*{References}" + "\n" + r"\textit{Available upon request.}" + "\n\n"

    doc = (
        _ROBOTICS_PREAMBLE
        + header
        + profile
        + education
        + experience
        + pubs
        + projects
        + skills
        + ref_tex
        + r"\end{document}"
        + "\n"
    )
    return doc


def _render_template_1(resume_json: dict[str, Any]) -> str:
    d = _resume_fields(resume_json)
    edu = []
    for e in d["education"][:3]:
        edu.append(
            f"\\item \\textbf{{{_esc(e.get('degree') or '')}}} - {_esc(e.get('institution') or '')} ({_esc(e.get('year') or '')})"
        )
    exp = []
    for e in d["experience"][:4]:
        bullets = e.get("bullets") or []
        b = "\\\\ ".join(_esc(x) for x in bullets[:2])
        exp.append(
            f"\\item \\textbf{{{_esc(e.get('title') or '')}}} at {_esc(e.get('company') or '')} ({_esc(e.get('start_date') or '')} -- {_esc(e.get('end_date') or '')})\\\\ {b}"
        )
    skills = " \\quad ".join(f"\\texttt{{{x}}}" for x in (d["skills"] or ["Python"]))
    return f"""\\documentclass[10pt,a4paper,ragged2e]{{maltacv}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{tgheros}}
\\renewcommand*\\familydefault{{\\sfdefault}}
\\name{{{d['name']}}}
\\firstname{{{d['name'].split(' ')[0] if d['name'] else 'Candidate'}}}
\\familyname{{}}
\\begin{{document}}
\\tagline{{AI-generated resume}}
\\personalinfo{{\\email{{{d['email']}}} \\linkedin{{{d['linkedin']}}} \\github{{{d['github']}}} \\phone{{{d['phone']}}}}}
\\bio{{{d['summary']}}}
\\makecvheader
\\cvsection{{Skills}}
{skills}
\\cvsection{{Education}}
\\begin{{itemize}}
{chr(10).join(edu) if edu else "\\item Add education"}
\\end{{itemize}}
\\cvsection{{Experience}}
\\begin{{itemize}}
{chr(10).join(exp) if exp else "\\item Add experience"}
\\end{{itemize}}
\\end{{document}}
"""


def _render_template_2(resume_json: dict[str, Any]) -> str:
    d = _resume_fields(resume_json)
    proj = []
    for p in d["projects"][:4]:
        proj.append(f"\\item \\textbf{{{_esc(p.get('name') or '')}}}: {_esc(p.get('description') or '')}")
    exp = []
    for e in d["experience"][:4]:
        exp.append(
            f"\\item \\textbf{{{_esc(e.get('title') or '')}}} | {_esc(e.get('company') or '')} | {_esc(e.get('start_date') or '')} -- {_esc(e.get('end_date') or '')}"
        )
    return f"""\\documentclass[a4paper,11pt]{{article}}
\\usepackage[margin=0.7in]{{geometry}}
\\usepackage[hidelinks]{{hyperref}}
\\begin{{document}}
\\begin{{center}}
{{\\LARGE \\textbf{{{d['name']}}}}}\\\\
{d['email']} \\quad {d['phone']}\\\\
{d['linkedin']} \\quad {d['github']}
\\end{{center}}
\\section*{{Summary}}
{d['summary']}
\\section*{{Experience}}
\\begin{{itemize}}
{chr(10).join(exp) if exp else "\\item Add experience"}
\\end{{itemize}}
\\section*{{Projects}}
\\begin{{itemize}}
{chr(10).join(proj) if proj else "\\item Add projects"}
\\end{{itemize}}
\\section*{{Technical Skills}}
{", ".join(d["skills"] or ["Python"])}
\\end{{document}}
"""


def _render_template_ats(resume_json: dict[str, Any]) -> str:
    """Clean sans-serif resume with teal accents, header rule, and grey metadata (matches polished PDF look)."""
    d = _resume_fields(resume_json)
    sk = resume_json.get("skills") or {}
    tech = [str(x).strip() for x in (sk.get("technical") or []) if str(x).strip()]
    tools = [str(x).strip() for x in (sk.get("tools") or []) if str(x).strip()]
    soft = [str(x).strip() for x in (sk.get("soft") or []) if str(x).strip()]
    certs = [str(x).strip() for x in (sk.get("certifications") or []) if str(x).strip()]
    merged = list(dict.fromkeys(tech + tools))[:45]
    skill_str = ", ".join(_esc(x) for x in merged) if merged else _esc("Add skills in Enhance tab")
    soft_str = ", ".join(_esc(x) for x in soft[:16]) if soft else ""
    cert_str = ", ".join(_esc(x) for x in certs[:12]) if certs else ""

    contact_primary: list[str] = []
    if d["phone"]:
        contact_primary.append(d["phone"])
    if d["email"]:
        contact_primary.append(d["email"])
    contact_links: list[str] = []
    if d["linkedin"]:
        contact_links.append(d["linkedin"])
    if d["github"]:
        contact_links.append(d["github"])

    exp_blocks: list[str] = []
    for e in d["experience"][:8]:
        title = _esc(str(e.get("title") or "").strip())
        company = _esc(str(e.get("company") or "").strip())
        sd = _esc(str(e.get("start_date") or "").strip())
        ed = _esc(str(e.get("end_date") or "").strip())
        span = f"{sd} -- {ed}" if sd or ed else ""
        bullets = [_norm_line(b) for b in (e.get("bullets") or []) if _norm_line(b)]
        if not bullets:
            bullets = [_norm_line(b) for b in (e.get("description") or []) if _norm_line(b)]
        head = f"\\noindent\\textbf{{{title}}}"
        if company:
            head += f"\\ {{\\color{{accent}}$\\cdot$}}\\ \\textit{{{company}}}"
        if span:
            head += f" \\hfill {{\\color{{muted}}\\small ({span})}}"
        lines = [head + r"\\"]
        if bullets:
            lines.append(r"\begin{itemize}\setlength{\itemsep}{2pt}\setlength{\topsep}{4pt}")
            lines.extend(f"  \\item {_esc(b)}" for b in bullets[:12])
            lines.append(r"\end{itemize}")
        lines.append(r"\vspace{0.45em}")
        exp_blocks.append("\n".join(lines))

    edu_items: list[str] = []
    for e in d["education"][:6]:
        deg = _esc(str(e.get("degree") or "").strip())
        fld = _esc(str(e.get("field") or "").strip())
        inst = _esc(str(e.get("institution") or "").strip())
        yr = _esc(str(e.get("year") or "").strip())
        gpa = e.get("gpa")
        line = f"\\item \\textbf{{{deg}}}"
        if fld:
            line += f", {fld}"
        if inst:
            line += f" \\textemdash\\ \\textit{{{inst}}}"
        tail = []
        if yr:
            tail.append(yr)
        if gpa not in (None, ""):
            tail.append(f"GPA: {_esc(str(gpa))}")
        if tail:
            tail_txt = " · ".join(tail)
            line += f" \\hfill {{\\color{{muted}}\\small ({tail_txt})}}"
        edu_items.append(line)

    proj_items: list[str] = []
    for p in d["projects"][:6]:
        nm = _esc(str(p.get("name") or "").strip())
        desc = _esc(_norm_line(str(p.get("description") or "")))
        ts = ", ".join(_esc(str(t)) for t in (p.get("tech_stack") or [])[:8] if str(t).strip())
        chunk = f"\\item \\textbf{{{nm}}}"
        if ts:
            chunk += f" ({ts})"
        if desc:
            chunk += f" {desc}"
        proj_items.append(chunk)

    pubs = [_esc(str(p).strip()) for p in (resume_json.get("publications") or []) if str(p).strip()][:10]
    langs = [_esc(str(x).strip()) for x in (resume_json.get("languages") or []) if str(x).strip()]

    summary_tex = d["summary"] if d["summary"] else r"\textit{—}"

    body: list[str] = [
        r"\documentclass[a4paper,11pt]{article}",
        r"\usepackage[margin=0.75in]{geometry}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{helvet}",
        r"\renewcommand{\familydefault}{\sfdefault}",
        r"\usepackage{xcolor}",
        r"\definecolor{accent}{HTML}{0e7490}",
        r"\definecolor{muted}{HTML}{6b7280}",
        r"\usepackage{enumitem}",
        r"\usepackage{multicol}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\newcommand{\cvsect}[1]{\vspace{0.55em}\noindent\textcolor{accent}{\large\bfseries #1}\par\vspace{0.28em}}",
        r"\setlist[itemize]{leftmargin=*, nosep, topsep=2pt, parsep=0pt, itemsep=2pt}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{0.32em}",
        r"\begin{document}",
        r"{\LARGE\bfseries\textcolor{accent}{" + d["name"] + r"}}\\[0.25em]",
    ]
    if d["location"]:
        body.append(r"{\color{muted}\small " + d["location"] + r"}\\[0.35em]")
    if contact_primary:
        body.append(r"{\small " + " \\textbullet{} ".join(contact_primary) + r"}\\")
    if contact_links:
        body.append(r"{\small " + " \\textbullet{} ".join(contact_links) + r"}\\")
    body.append(r"\vspace{0.2em}\textcolor{accent}{\rule{\linewidth}{0.9pt}}\\[0.65em]")
    body.extend([r"\cvsect{Summary}", summary_tex + r"\\[0.35em]"])
    body.extend(
        [
            r"\cvsect{Experience}",
            r"\vspace{-0.15em}",
        ]
    )
    if exp_blocks:
        body.append("\n".join(exp_blocks))
    else:
        body.append(r"\textit{No experience listed.}" + r"\\")
    body.extend([r"\cvsect{Education}", r"\vspace{-0.15em}"])
    if edu_items:
        body.append(r"\begin{itemize}")
        body.extend(edu_items)
        body.append(r"\end{itemize}")
    else:
        body.append(r"\textit{No education listed.}" + r"\\")
    body.append(r"\cvsect{Skills}")
    body.append(r"\vspace{-0.15em}")
    if len(merged) > 10:
        body.append(r"\begin{multicols}{2}")
        body.append(r"\begin{itemize}[itemsep=1pt,topsep=0pt]")
        for s in merged:
            body.append(f"  \\item {{\\small {_esc(s)}}}")
        body.append(r"\end{itemize}")
        body.append(r"\end{multicols}")
    else:
        body.append(skill_str + r"\\")
    if soft_str:
        body.extend([r"\textit{Professional:} " + soft_str + r"\\"])
    if cert_str:
        body.extend([r"\textit{Certifications:} " + cert_str + r"\\"])
    if langs:
        body.append(r"\textit{Languages:} " + ", ".join(langs) + r"\\")
    if proj_items:
        body.extend([r"\cvsect{Projects}", r"\vspace{-0.15em}", r"\begin{itemize}"])
        body.extend(proj_items)
        body.append(r"\end{itemize}")
    if pubs:
        body.extend([r"\cvsect{Publications}", r"\vspace{-0.15em}", r"\begin{itemize}"])
        body.extend(f"\\item {p}" for p in pubs)
        body.append(r"\end{itemize}")
    body.append(r"\end{document}")
    return "\n".join(body) + "\n"


def _render_template_ats_variant(
    resume_json: dict[str, Any],
    *,
    accent_hex: str,
    muted_hex: str = "6b7280",
    margin_in: str = "0.75",
    compact: bool = False,
) -> str:
    tex = _render_template_ats(resume_json)
    tex = tex.replace(r"\definecolor{accent}{HTML}{0e7490}", rf"\definecolor{{accent}}{{HTML}}{{{accent_hex}}}")
    tex = tex.replace(r"\definecolor{muted}{HTML}{6b7280}", rf"\definecolor{{muted}}{{HTML}}{{{muted_hex}}}")
    tex = tex.replace(r"\usepackage[margin=0.75in]{geometry}", rf"\usepackage[margin={margin_in}in]{{geometry}}")
    if compact:
        tex = tex.replace(r"\setlength{\parskip}{0.32em}", r"\setlength{\parskip}{0.16em}")
        tex = tex.replace(
            r"\setlist[itemize]{leftmargin=*, nosep, topsep=2pt, parsep=0pt, itemsep=2pt}",
            r"\setlist[itemize]{leftmargin=*, nosep, topsep=1pt, parsep=0pt, itemsep=1pt}",
        )
    return tex


def _render_template_executive_navy(resume_json: dict[str, Any]) -> str:
    tex = _render_template_ats_variant(
        resume_json,
        accent_hex="1e3a8a",
        muted_hex="475569",
        margin_in="0.78",
        compact=False,
    )
    tex = tex.replace(r"\cvsect{Summary}", r"\cvsect{Executive Summary}")
    return tex


def _render_template_slate_minimal(resume_json: dict[str, Any]) -> str:
    return _render_template_ats_variant(
        resume_json,
        accent_hex="334155",
        muted_hex="6b7280",
        margin_in="0.80",
        compact=True,
    )


def _render_template_data_compact(resume_json: dict[str, Any]) -> str:
    tex = _render_template_ats_variant(
        resume_json,
        accent_hex="0f766e",
        muted_hex="4b5563",
        margin_in="0.62",
        compact=True,
    )
    tex = tex.replace(r"\cvsect{Summary}", r"\cvsect{Profile Snapshot}")
    return tex


def _render_template_modern_emerald(resume_json: dict[str, Any]) -> str:
    return _render_template_ats_variant(
        resume_json,
        accent_hex="047857",
        muted_hex="6b7280",
        margin_in="0.72",
        compact=False,
    )


def render_resume_latex(template_id: str, resume_json: dict[str, Any]) -> str:
    from app.services.accent_colors import accent_from_resume, apply_accent_to_latex_preamble

    if template_id == LATEX_TEMPLATE_2:
        tex = _render_template_2(resume_json)
    elif template_id == LATEX_TEMPLATE_ROBOTICS:
        tex = _render_template_robotics(resume_json)
    elif template_id == LATEX_TEMPLATE_ATS:
        tex = _render_template_ats(resume_json)
    elif template_id == LATEX_TEMPLATE_EXECUTIVE:
        tex = _render_template_executive_navy(resume_json)
    elif template_id == LATEX_TEMPLATE_SLATE:
        tex = _render_template_slate_minimal(resume_json)
    elif template_id == LATEX_TEMPLATE_DATA:
        tex = _render_template_data_compact(resume_json)
    elif template_id == LATEX_TEMPLATE_EMERALD:
        tex = _render_template_modern_emerald(resume_json)
    else:
        tex = _render_template_1(resume_json)

    # Apply user accent on top of template defaults.
    hex6 = accent_from_resume(resume_json)
    m_begin = re.search(r"\\begin\s*\{\s*document\s*\}", tex, re.I)
    if m_begin:
        preamble = apply_accent_to_latex_preamble(tex[: m_begin.start()], resume_json)
        tex = preamble + tex[m_begin.start() :]
    else:
        tex = tex.replace(r"\definecolor{accent}{HTML}{0e7490}", rf"\definecolor{{accent}}{{HTML}}{{{hex6}}}")
        tex = tex.replace(r"\definecolor{accent}{HTML}{1e3a8a}", rf"\definecolor{{accent}}{{HTML}}{{{hex6}}}")
        tex = tex.replace(r"\definecolor{accent}{HTML}{334155}", rf"\definecolor{{accent}}{{HTML}}{{{hex6}}}")
        tex = tex.replace(r"\definecolor{accent}{HTML}{0f766e}", rf"\definecolor{{accent}}{{HTML}}{{{hex6}}}")
        tex = tex.replace(r"\definecolor{accent}{HTML}{047857}", rf"\definecolor{{accent}}{{HTML}}{{{hex6}}}")
    return tex
