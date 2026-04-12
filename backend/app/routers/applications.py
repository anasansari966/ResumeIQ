from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import Application, ApplicationEvent, JobListing
from app.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut)
async def create_app(
    body: ApplicationCreate,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    job = await session.get(JobListing, body.job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    existing = await session.exec(
        select(Application).where(Application.user_id == user.id, Application.job_id == body.job_id)
    )
    row = existing.first()
    previous_status = ""
    event_note = "Application created"
    if row:
        previous_status = row.status
        row.resume_id = body.resume_id or row.resume_id
        row.status = body.status
        row.notes = body.notes or row.notes
        if body.status == "applied" and row.applied_at is None:
            row.applied_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        event_note = "Application updated"
    else:
        row = Application(
            user_id=user.id,
            job_id=body.job_id,
            resume_id=body.resume_id,
            status=body.status,
            notes=body.notes,
            applied_at=datetime.utcnow() if body.status == "applied" else None,
        )
        session.add(row)
        await session.flush()

    session.add(row)
    await session.flush()
    session.add(
        ApplicationEvent(
            application_id=row.id or 0,
            user_id=user.id,
            from_status=previous_status,
            to_status=body.status,
            note=event_note,
        )
    )
    await session.commit()
    await session.refresh(row)
    return ApplicationOut(
        id=row.id,
        user_id=row.user_id,
        job_id=row.job_id,
        resume_id=row.resume_id,
        status=row.status,
        notes=row.notes,
        applied_at=row.applied_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[ApplicationOut])
async def list_apps(user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    res = await session.exec(select(Application).where(Application.user_id == user.id))
    rows = res.all()
    return [
        ApplicationOut(
            id=r.id,
            user_id=r.user_id,
            job_id=r.job_id,
            resume_id=r.resume_id,
            status=r.status,
            notes=r.notes,
            applied_at=r.applied_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.patch("/{app_id}", response_model=ApplicationOut)
async def update_app(
    app_id: int,
    body: ApplicationUpdate,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    row = await session.get(Application, app_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Not found")
    previous_status = row.status
    if body.status is not None:
        row.status = body.status
    if body.notes is not None:
        row.notes = body.notes
    if body.applied_at is not None:
        row.applied_at = body.applied_at
    row.updated_at = datetime.utcnow()
    session.add(row)
    if body.status is not None and body.status != previous_status:
        session.add(
            ApplicationEvent(
                application_id=row.id or 0,
                user_id=user.id,
                from_status=previous_status,
                to_status=body.status,
                note=body.notes or "",
            )
        )
    await session.commit()
    await session.refresh(row)
    return ApplicationOut(
        id=row.id,
        user_id=row.user_id,
        job_id=row.job_id,
        resume_id=row.resume_id,
        status=row.status,
        notes=row.notes,
        applied_at=row.applied_at,
        updated_at=row.updated_at,
    )
