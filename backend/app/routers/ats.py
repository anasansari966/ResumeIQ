from fastapi import APIRouter

from app.schemas import ATSScoreIn, ATSScoreOut
from app.services.ats_engine import score_resume_jd

router = APIRouter(prefix="/api/v1/ats", tags=["ats"])


@router.post("/score", response_model=ATSScoreOut)
async def ats_score(body: ATSScoreIn):
    jd_keywords = body.jd_keywords
    if body.jd_analysis:
        jd_keywords = body.jd_analysis.get("must_have_keywords") or body.jd_analysis.get("keywords") or jd_keywords
    overall, dims, suggestions = score_resume_jd(body.resume_json, jd_text="", jd_keywords=jd_keywords or None)
    return ATSScoreOut(overall=overall, dimensions=dims, suggestions=suggestions)
