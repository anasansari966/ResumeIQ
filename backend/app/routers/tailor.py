import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import JDAnalysis, Resume, TailoringSession
from app.schemas import TailorSessionOut, TailorStartIn
from app.services.ats_engine import score_resume_jd
from app.services.resume_export import export_resume_pdf
from app.services.template_registry import first_resume_template_id
from app.services.resume_generator import generate_tailored_resume, stream_tailored_resume_tokens

router = APIRouter(prefix="/api/v1/tailor", tags=["tailor"])


@router.get("/stream/preview")
async def stream_preview(
    resume_id: int,
    jd_analysis_id: int,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    resume = await db.get(Resume, resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    jd_row = await db.get(JDAnalysis, jd_analysis_id)
    if not jd_row or jd_row.user_id != user.id:
        raise HTTPException(404, "JD analysis not found")

    async def gen():
        buf = ""
        async for chunk in stream_tailored_resume_tokens(resume.parsed_json, jd_row.parsed_json, jd_row.raw_jd):
            buf += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True, 'buffer': buf})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("", response_model=TailorSessionOut)
async def start_tailor(
    body: TailorStartIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    resume = await db.get(Resume, body.resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    jd_row = await db.get(JDAnalysis, body.jd_analysis_id)
    if not jd_row or jd_row.user_id != user.id:
        raise HTTPException(404, "JD analysis not found")

    out = await generate_tailored_resume(resume.parsed_json, jd_row.parsed_json, jd_row.raw_jd)
    kws = jd_row.parsed_json.get("must_have_keywords") or jd_row.parsed_json.get("keywords") or []
    overall, _, _ = score_resume_jd(out, jd_text=jd_row.raw_jd, jd_keywords=kws)

    tid = (body.template_id or "").strip() or (resume.active_template_id or "").strip() or first_resume_template_id()
    ts = TailoringSession(
        resume_id=resume.id,
        jd_id=jd_row.id,
        output_resume_json=out,
        ats_score=overall,
        template_id=tid,
        status="complete",
        updated_at=datetime.utcnow(),
    )
    db.add(ts)
    await db.commit()
    await db.refresh(ts)
    return TailorSessionOut(
        id=ts.id,
        resume_id=ts.resume_id,
        jd_id=ts.jd_id,
        output_resume_json=ts.output_resume_json,
        ats_score=ts.ats_score,
        template_id=ts.template_id,
        status=ts.status,
        created_at=ts.created_at,
    )


@router.get("/{session_id}", response_model=TailorSessionOut)
async def get_tailor_session(
    session_id: int,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    ts = await db.get(TailoringSession, session_id)
    if not ts:
        raise HTTPException(404, "Session not found")
    r = await db.get(Resume, ts.resume_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Session not found")
    return TailorSessionOut(
        id=ts.id,
        resume_id=ts.resume_id,
        jd_id=ts.jd_id,
        output_resume_json=ts.output_resume_json,
        ats_score=ts.ats_score,
        template_id=ts.template_id,
        status=ts.status,
        created_at=ts.created_at,
    )


@router.get("/{session_id}/pdf")
async def download_pdf(
    session_id: int,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    template_id: str | None = None,
):
    ts = await db.get(TailoringSession, session_id)
    if not ts:
        raise HTTPException(404, "Session not found")
    r = await db.get(Resume, ts.resume_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Session not found")
    tid = template_id or ts.template_id
    pdf_bytes = export_resume_pdf(ts.output_resume_json or {}, tid)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="resumeiq-{session_id}.pdf"'},
    )
