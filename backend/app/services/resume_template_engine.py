from __future__ import annotations

from typing import Any

from app.services.folder_templates import render_folder_template_latex
from app.services.latex_templates import render_resume_latex
from app.services.template_registry import get_template_descriptor, is_folder_template_id


def render_resume_template_tex(template_id: str, resume_json: dict[str, Any]) -> str:
    if is_folder_template_id(template_id):
        return render_folder_template_latex(template_id, resume_json)
    return render_resume_latex(template_id, resume_json)


def template_preview_context(template_id: str) -> dict[str, str]:
    desc = get_template_descriptor(template_id)
    if not desc:
        return {
            "name": template_id,
            "description": "Resume preview",
            "variant": "clean",
            "style": "Template",
        }
    return {
        "name": desc.name,
        "description": desc.best_for or desc.description or "Resume template preview",
        "variant": desc.preview_variant,
        "style": desc.style,
    }
