from html import escape
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import Resume
from app.schemas import TemplateMeta
from app.services.resume_template_engine import template_preview_context
from app.services.template_catalog import list_active_template_catalog
from app.services.template_registry import get_template_descriptor, is_supported_template_id

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


def _preview_seed(data: dict[str, Any] | None) -> dict[str, Any]:
    src = data or {}
    contact = src.get("contact") or {}
    experience = [row for row in (src.get("experience") or []) if isinstance(row, dict)]
    education = [row for row in (src.get("education") or []) if isinstance(row, dict)]
    skills = src.get("skills") or {}
    summary = str(src.get("summary") or "").strip()

    name = str(contact.get("name") or "").strip() or "Candidate Name"
    headline = ""
    if experience:
        headline = str(experience[0].get("title") or "").strip()
    if not headline:
        headline = "Professional Resume"

    return {
        "name": name,
        "headline": headline,
        "email": str(contact.get("email") or "").strip() or "candidate@example.com",
        "phone": str(contact.get("phone") or "").strip() or "+1 555 010 2026",
        "location": str(contact.get("location") or "").strip() or "Open to remote and hybrid roles",
        "linkedin": str(contact.get("linkedin") or "").strip(),
        "summary": summary or "A focused summary will appear here after resume parsing or editing.",
        "skills": [str(item).strip() for item in (skills.get("technical") or []) if str(item).strip()][:12]
        or ["Python", "SQL", "FastAPI", "React"],
        "experience": experience[:4],
        "education": education[:3],
    }


def _render_sidebar_classic(template_name: str, description: str, payload: dict[str, Any]) -> str:
    exp_html = "".join(
        f"""
        <div class="row-item">
          <p class="row-meta">{escape(str(item.get("start_date") or ""))} - {escape(str(item.get("end_date") or "Present"))}</p>
          <p class="row-title">{escape(str(item.get("title") or "Experience"))}</p>
          <p class="row-sub">{escape(str(item.get("company") or ""))}</p>
          <ul>
            {''.join(f"<li>{escape(str(b))}</li>" for b in (item.get("bullets") or item.get("description") or [])[:4] if str(b).strip())}
          </ul>
        </div>
        """
        for item in payload["experience"]
    )
    edu_html = "".join(
        f"""
        <div class="row-item compact">
          <p class="row-meta">{escape(str(item.get("year") or ""))}</p>
          <p class="row-title">{escape(str(item.get("degree") or ""))}</p>
          <p class="row-sub">{escape(str(item.get("institution") or ""))}</p>
        </div>
        """
        for item in payload["education"]
    )
    skill_html = "".join(f"<span class='pill'>{escape(skill)}</span>" for skill in payload["skills"])
    links = [payload["email"], payload["phone"], payload["location"]]
    if payload["linkedin"]:
        links.append(payload["linkedin"])
    side_html = "".join(f"<p>{escape(item)}</p>" for item in links if item)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(template_name)} preview</title>
  <style>
    body {{ margin: 0; background: #dbe4f2; font-family: 'Segoe UI', system-ui, sans-serif; color: #14213d; }}
    .frame {{ min-height: 100vh; padding: 18px; }}
    .paper {{ max-width: 860px; margin: 0 auto; background: #fff; box-shadow: 0 18px 50px rgba(15,23,42,.18); display: grid; grid-template-columns: 220px 1fr; position: relative; }}
    .paper::after {{ content: ""; position: absolute; top: 18px; bottom: 18px; left: 236px; border-left: 2px dotted #2563eb; }}
    .side {{ padding: 28px 22px; text-align: right; color: #334155; background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%); }}
    .side h2 {{ margin: 0 0 16px; font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: #1d4ed8; }}
    .side p {{ margin: 0 0 8px; font-size: 12px; line-height: 1.45; }}
    .main {{ padding: 30px 34px 34px 34px; }}
    .eyebrow {{ font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; }}
    h1 {{ margin: 2px 0 6px; color: #2563eb; font-size: 34px; line-height: 1.05; }}
    .headline {{ margin: 0 0 18px; font-size: 20px; font-weight: 700; color: #0f172a; }}
    .about {{ margin: 0 0 22px; font-size: 14px; line-height: 1.6; color: #334155; }}
    .section {{ margin-top: 18px; }}
    .section h3 {{ margin: 0 0 10px; font-size: 23px; font-weight: 800; color: #0f172a; }}
    .row-item {{ margin-bottom: 16px; }}
    .row-item.compact {{ margin-bottom: 12px; }}
    .row-meta {{ margin: 0 0 4px; font-size: 12px; color: #2563eb; font-weight: 700; }}
    .row-title {{ margin: 0; font-size: 14px; font-weight: 700; color: #0f172a; }}
    .row-sub {{ margin: 2px 0 6px; font-size: 13px; color: #475569; }}
    ul {{ margin: 0; padding-left: 18px; color: #475569; font-size: 13px; line-height: 1.5; }}
    .pill-wrap {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .pill {{ border: 1px solid rgba(37,99,235,.14); background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 600; }}
    .banner {{ margin: 0 0 18px; border-radius: 14px; background: #eff6ff; color: #1d4ed8; padding: 10px 12px; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="frame">
    <div class="paper">
      <aside class="side">
        <h2>{escape(template_name)}</h2>
        {side_html}
      </aside>
      <main class="main">
        <p class="eyebrow">{escape(description)}</p>
        <h1>{escape(payload["name"])}</h1>
        <p class="headline">{escape(payload["headline"])}</p>
        <p class="banner">Classic sidebar layout inspired by the imported folder template.</p>
        <p class="about">{escape(payload["summary"])}</p>
        <section class="section">
          <h3>Education</h3>
          {edu_html or "<p class='row-sub'>Add education to populate this preview.</p>"}
        </section>
        <section class="section">
          <h3>Experience</h3>
          {exp_html or "<p class='row-sub'>Add experience to populate this preview.</p>"}
        </section>
        <section class="section">
          <h3>Skills</h3>
          <div class="pill-wrap">{skill_html}</div>
        </section>
      </main>
    </div>
  </div>
</body>
</html>"""


def _render_modern_preview(template_name: str, description: str, payload: dict[str, Any], variant: str) -> str:
    if variant == "research":
        accent = "#0ea5e9"
        accent_bg = "linear-gradient(135deg, #082f49 0%, #0f172a 100%)"
        shell_bg = "#e0f2fe"
    elif variant == "minimal":
        accent = "#7c3aed"
        accent_bg = "linear-gradient(135deg, #ede9fe 0%, #ffffff 100%)"
        shell_bg = "#f5f3ff"
    else:
        accent = "#0f766e"
        accent_bg = "linear-gradient(135deg, #ecfeff 0%, #ffffff 100%)"
        shell_bg = "#ecfeff"

    exp_html = "".join(
        f"""
        <article class="timeline-item">
          <div class="timeline-dot"></div>
          <div class="timeline-body">
            <p class="timeline-title">{escape(str(item.get("title") or "Experience"))}</p>
            <p class="timeline-sub">{escape(str(item.get("company") or ""))}</p>
            <p class="timeline-meta">{escape(str(item.get("start_date") or ""))} - {escape(str(item.get("end_date") or "Present"))}</p>
          </div>
        </article>
        """
        for item in payload["experience"]
    )
    edu_html = "".join(
        f"<li><strong>{escape(str(item.get('degree') or 'Education'))}</strong><span>{escape(str(item.get('institution') or ''))}</span></li>"
        for item in payload["education"]
    )
    skill_html = "".join(f"<span class='chip'>{escape(skill)}</span>" for skill in payload["skills"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(template_name)} preview</title>
  <style>
    body {{ margin: 0; background: {shell_bg}; font-family: 'Segoe UI', system-ui, sans-serif; color: #0f172a; }}
    .frame {{ min-height: 100vh; padding: 18px; }}
    .paper {{ max-width: 860px; margin: 0 auto; background: #fff; box-shadow: 0 18px 50px rgba(15,23,42,.14); border-radius: 22px; overflow: hidden; }}
    .hero {{ padding: 28px 34px 24px; background: {accent_bg}; }}
    .eyebrow {{ margin: 0 0 10px; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: {accent}; font-weight: 700; }}
    h1 {{ margin: 0; font-size: 32px; line-height: 1.05; }}
    .headline {{ margin: 8px 0 12px; font-size: 16px; font-weight: 700; color: #334155; }}
    .summary {{ margin: 0; max-width: 640px; font-size: 14px; line-height: 1.6; color: #334155; }}
    .contact {{ margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }}
    .contact span {{ border: 1px solid rgba(15,23,42,.08); background: rgba(255,255,255,.72); padding: 7px 10px; border-radius: 999px; font-size: 12px; }}
    .content {{ padding: 28px 34px 34px; display: grid; gap: 22px; }}
    .split {{ display: grid; gap: 22px; grid-template-columns: 1.2fr .8fr; }}
    h3 {{ margin: 0 0 12px; font-size: 14px; letter-spacing: .08em; text-transform: uppercase; color: {accent}; }}
    .section {{ border: 1px solid rgba(15,23,42,.06); border-radius: 18px; padding: 18px; }}
    .timeline-item {{ display: flex; gap: 14px; margin-bottom: 14px; }}
    .timeline-dot {{ width: 10px; height: 10px; margin-top: 7px; border-radius: 999px; background: {accent}; box-shadow: 0 0 0 5px rgba(15,118,110,.08); }}
    .timeline-title {{ margin: 0; font-size: 14px; font-weight: 700; }}
    .timeline-sub, .timeline-meta {{ margin: 3px 0 0; font-size: 12px; color: #64748b; }}
    .skills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ border-radius: 999px; background: {shell_bg}; color: {accent}; padding: 7px 10px; font-size: 12px; font-weight: 700; }}
    .edu-list {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }}
    .edu-list li {{ display: grid; gap: 2px; font-size: 13px; }}
    .edu-list span {{ color: #64748b; }}
  </style>
</head>
<body>
  <div class="frame">
    <div class="paper">
      <header class="hero">
        <p class="eyebrow">{escape(template_name)}</p>
        <h1>{escape(payload["name"])}</h1>
        <p class="headline">{escape(payload["headline"])}</p>
        <p class="summary">{escape(payload["summary"])}</p>
        <div class="contact">
          <span>{escape(payload["email"])}</span>
          <span>{escape(payload["phone"])}</span>
          <span>{escape(payload["location"])}</span>
        </div>
      </header>
      <main class="content">
        <section class="section">
          <h3>Why this template</h3>
          <p class="summary">{escape(description)}</p>
        </section>
        <div class="split">
          <section class="section">
            <h3>Experience</h3>
            {exp_html or "<p class='timeline-meta'>Add experience to populate this preview.</p>"}
          </section>
          <div class="section-stack">
            <section class="section">
              <h3>Skills</h3>
              <div class="skills">{skill_html}</div>
            </section>
            <section class="section">
              <h3>Education</h3>
              <ul class="edu-list">{edu_html or "<li><strong>Education</strong><span>Add education to populate this preview.</span></li>"}</ul>
            </section>
          </div>
        </div>
      </main>
    </div>
  </div>
</body>
</html>"""


def _render_template_preview_html(template_id: str, data: dict[str, Any] | None) -> str:
    payload = _preview_seed(data)
    ctx = template_preview_context(template_id)
    if ctx["variant"] == "sidebar-classic":
        return _render_sidebar_classic(ctx["name"], ctx["description"], payload)
    return _render_modern_preview(ctx["name"], ctx["description"], payload, ctx["variant"])


@router.get("", response_model=list[TemplateMeta])
async def list_templates(session: Annotated[AsyncSession, Depends(get_session)]):
    rows = await list_active_template_catalog(session)
    return [
        TemplateMeta(
            id=row.id,
            name=row.name,
            style=row.style,
            best_for=row.best_for,
            ats_score=row.ats_score,
            kind=row.kind,
            source=row.source,
            description=row.description,
            preview_variant=row.preview_variant,
            file_name=row.entry_path.split("\\")[-1] if row.entry_path else None,
        )
        for row in rows
    ]


@router.get("/{template_id}/preview-html", response_class=HTMLResponse)
async def template_preview_html(
    template_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    resume_id: int | None = None,
):
    """Responsive HTML preview used by the template picker and editor screens."""
    if not is_supported_template_id(template_id):
        raise HTTPException(404, "Template not found")

    desc = get_template_descriptor(template_id)
    if desc is None:
        raise HTTPException(404, "Template not found")

    data: dict[str, Any] | None = None
    if resume_id is not None:
        r = await db.get(Resume, resume_id)
        if not r or r.user_id != user.id or r.deleted:
            raise HTTPException(404, "Resume not found")
        data = dict(r.parsed_json or {})

    return HTMLResponse(content=_render_template_preview_html(template_id, data))
