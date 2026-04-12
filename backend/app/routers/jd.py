from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.deps import CurrentUser
from app.models_db import JDAnalysis
from app.schemas import JDAnalysisOut, JDAnalyzeIn
from app.services.jd_analysis import analyze_jd

router = APIRouter(prefix="/api/v1/jd", tags=["jd"])


@router.post("/analyze", response_model=JDAnalysisOut)
async def analyze(body: JDAnalyzeIn, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    parsed = analyze_jd(body.raw_jd)
    row = JDAnalysis(user_id=user.id, raw_jd=body.raw_jd, parsed_json=parsed)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return JDAnalysisOut(id=row.id, parsed_json=row.parsed_json, created_at=row.created_at)
