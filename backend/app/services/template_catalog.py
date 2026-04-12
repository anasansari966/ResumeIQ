from __future__ import annotations

from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models_db import TemplateCatalog
from app.services.template_registry import TemplateDescriptor, list_resume_templates


def _apply_descriptor(row: TemplateCatalog, desc: TemplateDescriptor, now: datetime) -> None:
    row.name = desc.name
    row.style = desc.style
    row.best_for = desc.best_for
    row.ats_score = desc.ats_score
    row.kind = desc.kind
    row.source = desc.source
    row.description = desc.description
    row.preview_variant = desc.preview_variant
    row.preview_asset = str(desc.preview_asset) if desc.preview_asset else None
    row.entry_path = str(desc.entry_path) if desc.entry_path else None
    row.folder_path = str(desc.folder_path) if desc.folder_path else None
    row.sort_order = desc.sort_order
    row.is_active = True
    row.updated_at = now


async def sync_template_catalog(session: AsyncSession) -> list[TemplateCatalog]:
    now = datetime.utcnow()
    active_ids: set[str] = set()

    for desc in list_resume_templates():
        active_ids.add(desc.id)
        row = await session.get(TemplateCatalog, desc.id)
        if row is None:
            row = TemplateCatalog(id=desc.id, created_at=now, updated_at=now)
        _apply_descriptor(row, desc, now)
        session.add(row)

    res = await session.exec(select(TemplateCatalog))
    existing = list(res.all())
    for row in existing:
        if row.id not in active_ids and row.is_active:
            row.is_active = False
            row.updated_at = now
            session.add(row)

    await session.commit()

    fresh = await session.exec(
        select(TemplateCatalog).where(TemplateCatalog.is_active == True).order_by(TemplateCatalog.sort_order)  # noqa: E712
    )
    return list(fresh.all())


async def list_active_template_catalog(session: AsyncSession) -> list[TemplateCatalog]:
    res = await session.exec(
        select(TemplateCatalog).where(TemplateCatalog.is_active == True).order_by(TemplateCatalog.sort_order)  # noqa: E712
    )
    rows = list(res.all())
    if rows:
        return rows
    return await sync_template_catalog(session)
