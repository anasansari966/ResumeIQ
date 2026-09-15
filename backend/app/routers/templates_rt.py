from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import Resume
from app.schemas import TemplateMeta
from app.services.latex_templates import render_resume_latex
from app.services.template_registry import is_supported_template_id, list_resume_templates

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("", response_model=list[TemplateMeta])
async def list_templates():
    """Only supported templates: Template 1 and Template 2 (LaTeX)."""
    return [
        TemplateMeta(
            id=desc.id,
            name=desc.name,
            style=desc.style,
            best_for=desc.best_for or desc.description,
            ats_score=desc.ats_score,
            kind=desc.kind,
            source=desc.source,
            description=desc.description,
            preview_variant=desc.preview_variant,
            file_name=desc.file_name,
        )
        for desc in list_resume_templates()
    ]


@router.get("/{template_id}/preview-html", response_class=HTMLResponse)
async def template_preview_html(
    template_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    resume_id: int | None = None,
):
    """HTML preview for LaTeX templates (filled when ``resume_id`` is provided)."""
    if not is_supported_template_id(template_id):
        raise HTTPException(404, "Template not found")

    data: dict = {}
    if resume_id is not None:
        r = await db.get(Resume, resume_id)
        if not r or r.user_id != user.id or r.deleted:
            raise HTTPException(404, "Resume not found")
        data = dict(r.parsed_json or {})

    try:
        tex = render_resume_latex(template_id, data or {})
        safe = (
            tex.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        body_html = f"<pre style='white-space:pre-wrap;font-family:Consolas,monospace'>{safe}</pre>"
    except Exception as e:
        raise HTTPException(500, f"Preview generation failed: {e}") from e
    wrapped = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Template preview</title>
  <style>
    body {{ margin: 0; padding: 16px; background: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    .paper {{ max-width: 820px; margin: 0 auto; background: #fff; padding: 28px 32px;
      box-shadow: 0 4px 24px rgba(15,23,42,.12); min-height: 400px; }}
    .paper table {{ border-collapse: collapse; width: 100%; }}
    .paper td, .paper th {{ vertical-align: top; padding: 6px 8px; }}
    .banner {{ font-size: 12px; color: #64748b; margin-bottom: 12px; }}
  </style>
</head>
<body>
  <div class="banner">ResumeIQ · LaTeX template preview{f" · Resume #{resume_id}" if resume_id else ""}</div>
  <div class="paper">{body_html}</div>
</body>
</html>"""
    return HTMLResponse(content=wrapped)
