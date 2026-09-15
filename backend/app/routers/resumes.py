import logging
import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import Resume, ResumeTemplateSelection
from app.schemas import GenerateSummaryIn, ResumeOut, ResumeTemplateSelectIn, ResumeUpdateIn
from app.services.ats_engine import score_resume_jd
from app.config import settings
from app.services.resume_enhance import generate_profile_summary_from_fields
from app.services.resume_export import export_resume_pdf_with_mode
from app.services.resume_finalize import (
    ensure_summary_if_missing,
    rule_normalize_resume,
    structure_resume_for_ats_template,
)
from app.services.resume_parser import parse_upload
from app.services.resume_salvage import comprehensive_salvage
from app.services.resume_template_engine import render_resume_template_tex
from app.services.template_registry import first_resume_template_id, get_template_descriptor, is_supported_template_id

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])
log = logging.getLogger(__name__)


def _attachment_filename(resume_id: int, template_id: str, ext: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", (template_id or "resume").strip("_"))[:48] or "resume"
    return f"resume-{resume_id}-{slug}.{ext}"


def _blend_ats_with_template(content_score: float, template_id: str) -> float:
    tid = (template_id or "").strip() or first_resume_template_id()
    desc = get_template_descriptor(tid)
    template_ats = float(desc.ats_score) if desc and getattr(desc, "ats_score", None) is not None else 94.0
    return round(min(100.0, 0.42 * float(content_score) + 0.58 * template_ats), 1)


def _resume_out(r: Resume) -> ResumeOut:
    fn = (r.file_url or "").strip() or None
    return ResumeOut(
        id=r.id,
        user_id=r.user_id,
        parsed_json=r.parsed_json,
        ats_baseline=r.ats_baseline,
        active_template_id=r.active_template_id or "",
        created_at=r.created_at,
        updated_at=r.updated_at,
        file_name=fn,
    )


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    parsed = await parse_upload(file.filename or "resume.pdf", data)
    overall, _, _ = score_resume_jd(parsed, jd_text="")
    parsed["ats_score_baseline"] = overall
    r = Resume(
        user_id=user.id,
        parsed_json=parsed,
        ats_baseline=overall,
        active_template_id=first_resume_template_id(),
        file_url=file.filename,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return _resume_out(r)


@router.post("/{resume_id}/generate-summary", response_model=ResumeOut)
async def generate_ai_summary(
    resume_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    body: GenerateSummaryIn | None = None,
):
    """2–3 line Summary/Objective from structured fields (OpenAI). Optional body.parsed_json merges current draft."""
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    base = dict(r.parsed_json or {})
    meta = base.get("_resumeiq_cleaned") or ""
    if body and body.parsed_json:
        inbox = dict(body.parsed_json)
        for k in list(inbox.keys()):
            if str(k).startswith("_resumeiq"):
                del inbox[k]
        merged = {**base, **inbox}
        if meta:
            merged["_resumeiq_cleaned"] = meta
    else:
        merged = dict(base)
    try:
        text = await generate_profile_summary_from_fields(merged)
    except ValueError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Summary generation failed: {e}") from e
    merged["summary"] = text
    merged["summary_origin"] = "model"
    merged = comprehensive_salvage(merged, meta)
    try:
        merged = rule_normalize_resume(merged, meta)
    except Exception:
        raise HTTPException(400, "Invalid resume JSON after summary merge") from None
    overall, _, _ = score_resume_jd(merged, jd_text="")
    merged["ats_score_baseline"] = overall
    r.parsed_json = merged
    r.ats_baseline = overall
    r.updated_at = datetime.utcnow()
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return _resume_out(r)


@router.get("/{resume_id}/export-docx")
async def export_resume_docx(
    resume_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Legacy endpoint; product now uses LaTeX templates only."""
    raise HTTPException(400, "DOCX export disabled. Use /export-tex or /export-pdf.")


@router.get("/{resume_id}/export-tex")
async def export_resume_tex(
    resume_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    template_id: str | None = None,
):
    """Export AI-editable LaTeX source using the active template."""
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    requested = (template_id or "").strip()
    if requested and not is_supported_template_id(requested):
        raise HTTPException(404, "Template not found")
    tid = requested or (r.active_template_id or "").strip() or first_resume_template_id()
    tex = render_resume_template_tex(tid, dict(r.parsed_json or {}))
    fn = _attachment_filename(resume_id, tid, "tex")
    return Response(
        content=tex.encode("utf-8"),
        media_type="text/x-tex; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.get("/{resume_id}/export-pdf")
async def export_resume_pdf_endpoint(
    resume_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    template_id: str | None = None,
):
    """PDF from current resume JSON (Word path when available, else built-in PDF)."""
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    requested = (template_id or "").strip()
    if requested and not is_supported_template_id(requested):
        raise HTTPException(404, "Template not found")
    tid = requested or (r.active_template_id or "").strip() or first_resume_template_id()
    pdf_b, render_mode = export_resume_pdf_with_mode(dict(r.parsed_json or {}), tid)
    if pdf_b is None or render_mode == "latex_unavailable":
        raise HTTPException(
            status_code=503,
            detail="PDF could not be generated. Please try again.",
        )
    fn = _attachment_filename(resume_id, tid, "pdf")
    return Response(
        content=pdf_b,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{fn}"',
            "X-ResumeIQ-Render-Mode": render_mode,
            "X-ResumeIQ-Template-Id": tid,
        },
    )


@router.get("", response_model=list[ResumeOut])
async def list_resumes(user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    result = await session.exec(select(Resume).where(Resume.user_id == user.id, Resume.deleted == False))  # noqa: E712
    rows = result.all()
    return [_resume_out(r) for r in rows]


@router.post("/{resume_id}/select-template", response_model=ResumeOut)
async def select_resume_template(
    resume_id: int,
    body: ResumeTemplateSelectIn,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    if not is_supported_template_id(body.template_id):
        raise HTTPException(404, "Template not found")

    desc = get_template_descriptor(body.template_id)
    data = dict(r.parsed_json or {})
    cleaned = str(data.get("_resumeiq_cleaned") or "").strip()
    if not cleaned:
        # Recover text from stored fields so OpenAI can structure every section.
        for key in ("raw_text", "full_text", "text"):
            cleaned = str(data.get(key) or "").strip()
            if cleaned:
                break
    llm_note = ""

    if body.restructure:
        from app.services.llm_client import llm_key_diagnosis

        diag = llm_key_diagnosis()
        if not diag.get("ok"):
            # Fail fast with a clear client error instead of a generic 500.
            raise HTTPException(status_code=400, detail=str(diag.get("message") or "OpenAI is not configured correctly."))
        try:
            data = await structure_resume_for_ats_template(
                data,
                cleaned,
                template_name=desc.name if desc else body.template_id,
                template_style=desc.style if desc else "ATS",
            )
            if cleaned and not str(data.get("_resumeiq_cleaned") or "").strip():
                data["_resumeiq_cleaned"] = cleaned
            llm_note = "structured"
        except Exception as exc:  # noqa: BLE001
            log.exception("select-template LLM restructure failed")
            # Keep template selection working with deterministic cleanup.
            data = rule_normalize_resume(data, cleaned)
            llm_note = f"fallback:{exc}"

    try:
        content_score, _, _ = score_resume_jd(data, jd_text="")
        blended = _blend_ats_with_template(content_score, body.template_id)
        data["ats_score_baseline"] = blended
        data["active_template_id"] = body.template_id
        if llm_note:
            data["_resumeiq_llm_structure"] = llm_note
        if body.accent_color:
            from app.services.accent_colors import normalize_accent_hex

            data["accent_color"] = f"#{normalize_accent_hex(body.accent_color)}"
        r.parsed_json = data
        r.ats_baseline = blended
        r.active_template_id = body.template_id
        r.updated_at = datetime.utcnow()
        session.add(r)
        session.add(
            ResumeTemplateSelection(
                resume_id=r.id,
                user_id=user.id,
                template_id=body.template_id,
                template_name=desc.name if desc else body.template_id,
                source=desc.source if desc else "unknown",
            )
        )
        await session.commit()
        await session.refresh(r)
        return _resume_out(r)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("select-template failed")
        raise HTTPException(status_code=500, detail=f"Could not apply template: {exc}") from exc


@router.post("/{resume_id}/re-salvage", response_model=ResumeOut)
async def re_salvage_resume(
    resume_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Re-run deterministic salvage + normalization (uses stored _resumeiq_cleaned if present)."""
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    meta = (r.parsed_json or {}).get("_resumeiq_cleaned") or ""
    data = dict(r.parsed_json or {})
    data = comprehensive_salvage(data, meta)
    normalized = rule_normalize_resume(data, meta)
    from app.services.llm_client import llm_configured

    if llm_configured():
        normalized = await ensure_summary_if_missing(normalized, meta)
        normalized = rule_normalize_resume(normalized, meta)
    overall, _, _ = score_resume_jd(normalized, jd_text="")
    normalized["ats_score_baseline"] = overall
    r.parsed_json = normalized
    r.ats_baseline = overall
    r.updated_at = datetime.utcnow()
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return _resume_out(r)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    r.deleted = True
    session.add(r)
    await session.commit()
    return {"ok": True, "id": resume_id}


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(resume_id: int, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    return _resume_out(r)


@router.patch("/{resume_id}", response_model=ResumeOut)
async def update_resume(
    resume_id: int,
    body: ResumeUpdateIn,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    r = await session.get(Resume, resume_id)
    if not r or r.user_id != user.id or r.deleted:
        raise HTTPException(404, "Resume not found")
    meta = (r.parsed_json or {}).get("_resumeiq_cleaned")
    merged = {**body.parsed_json}
    if meta:
        merged["_resumeiq_cleaned"] = meta
    merged = comprehensive_salvage(merged, meta or "")
    try:
        normalized = rule_normalize_resume(merged, meta or "")
    except Exception:
        raise HTTPException(400, "Invalid resume JSON structure")
    from app.services.llm_client import llm_configured

    if llm_configured():
        normalized = await ensure_summary_if_missing(normalized, meta or "")
        normalized = rule_normalize_resume(normalized, meta or "")
    r.parsed_json = normalized
    r.updated_at = datetime.utcnow()
    if body.recalc_ats:
        overall, _, _ = score_resume_jd(normalized, jd_text="")
        blended = _blend_ats_with_template(overall, (r.active_template_id or "").strip())
        normalized["ats_score_baseline"] = blended
        r.parsed_json = normalized
        r.ats_baseline = blended
    elif normalized.get("ats_score_baseline") is not None:
        try:
            r.ats_baseline = float(normalized["ats_score_baseline"])
        except (TypeError, ValueError):
            pass
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return _resume_out(r)
