"""Resume export: Word templates from disk when possible; otherwise a minimal ReportLab PDF."""
from __future__ import annotations

import logging
from typing import Any

from app.services.docx_export import docx_to_pdf_bytes, fill_resume_docx
from app.services.latex_export import latex_to_pdf_bytes
from app.services.latex_templates import is_latex_template_id
from app.services.pdf_templates import build_pdf
from app.services.resume_template_engine import render_resume_template_tex
from app.services.template_registry import (
    docx_path_for_id,
    is_docx_template_id,
    is_folder_template_id,
    zip_packaged_template_build_dir,
)

log = logging.getLogger(__name__)


def export_resume_pdf(resume_json: dict[str, Any], template_id: str) -> bytes:
    pdf_bytes, mode = export_resume_pdf_with_mode(resume_json, template_id)
    if pdf_bytes is None:
        raise RuntimeError("LaTeX PDF export is not available for this template on the server.")
    return pdf_bytes


def export_resume_pdf_with_mode(resume_json: dict[str, Any], template_id: str) -> tuple[bytes | None, str]:
    """Return (pdf_bytes, mode). Always prefers a downloadable PDF over failing on LaTeX gaps."""
    tid = template_id
    latex_track = is_folder_template_id(tid) or is_latex_template_id(tid)
    if latex_track:
        try:
            tex = render_resume_template_tex(tid, resume_json)
            build_dir = zip_packaged_template_build_dir(tid)
            pdf = latex_to_pdf_bytes(tex, build_dir=build_dir) if build_dir else latex_to_pdf_bytes(tex)
            if pdf:
                return pdf, "latex"
        except Exception:  # noqa: BLE001
            log.exception("LaTeX PDF rendering failed for template %s; using built-in PDF", tid)
        # Never block the user on missing MiKTeX packages / GUI installer — fall back to structured PDF.
        return build_pdf(resume_json, tid), "reportlab_fallback"
    if is_docx_template_id(tid):
        path = docx_path_for_id(tid)
        if path:
            docx_b = fill_resume_docx(path, resume_json)
            pdf = docx_to_pdf_bytes(docx_b)
            if pdf:
                return pdf, "docx"
    return build_pdf(resume_json, tid), "reportlab"
