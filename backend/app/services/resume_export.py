"""Resume export: Word templates from disk when possible; otherwise a minimal ReportLab PDF."""
from __future__ import annotations

from typing import Any

from app.services.docx_export import docx_to_pdf_bytes, fill_resume_docx
from app.services.latex_export import latex_to_pdf_bytes
from app.services.latex_templates import is_latex_template_id
from app.services.pdf_templates import build_pdf
from app.services.resume_template_engine import render_resume_template_tex
from app.services.template_registry import docx_path_for_id, is_docx_template_id, is_folder_template_id


def export_resume_pdf(resume_json: dict[str, Any], template_id: str) -> bytes:
    tid = template_id
    if is_folder_template_id(tid) or is_latex_template_id(tid):
        tex = render_resume_template_tex(tid, resume_json)
        pdf = latex_to_pdf_bytes(tex)
        if pdf:
            return pdf
    if is_docx_template_id(tid):
        path = docx_path_for_id(tid)
        if path:
            docx_b = fill_resume_docx(path, resume_json)
            pdf = docx_to_pdf_bytes(docx_b)
            if pdf:
                return pdf
    return build_pdf(resume_json, tid)
