from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = ""


class UserPublic(BaseModel):
    id: int
    email: str
    name: str
    plan: str


class RegisterOut(BaseModel):
    ok: bool = True
    user_id: int
    email: str
    email_verification_required: bool = True
    message: str = "OTP sent to your email"
    dev_otp: Optional[str] = None


class VerifyOtpIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=10)


class ResendOtpIn(BaseModel):
    email: EmailStr


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=6)


class ActionMessageOut(BaseModel):
    ok: bool = True
    message: str = ""
    dev_otp: Optional[str] = None


class ContactBlock(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    location: str = ""


def _coerce_resume_str(v: Any) -> str:
    """OpenAI JSON often returns years/dates as ints; schema uses strings everywhere."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


class ExperienceItem(BaseModel):
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)

    @field_validator("company", "title", "start_date", "end_date", mode="before")
    @classmethod
    def _string_scalar_fields(cls, v: Any) -> str:
        return _coerce_resume_str(v)

    @field_validator("description", "bullets", mode="before")
    @classmethod
    def _string_list_fields(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            s = _coerce_resume_str(v)
            return [s] if s else []
        out: list[str] = []
        for x in v:
            s = _coerce_resume_str(x)
            if s:
                out.append(s)
        return out


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    year: str = ""
    gpa: Optional[str] = None

    @field_validator("institution", "degree", "field", "year", mode="before")
    @classmethod
    def _education_strings(cls, v: Any) -> str:
        return _coerce_resume_str(v)

    @field_validator("gpa", mode="before")
    @classmethod
    def _gpa_optional(cls, v: Any) -> str | None:
        if v is None or v == "":
            return None
        s = _coerce_resume_str(v)
        return s if s else None


class SkillsBlock(BaseModel):
    technical: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    link: Optional[str] = None


class ResumeSchema(BaseModel):
    contact: ContactBlock = Field(default_factory=ContactBlock)
    summary: str = ""
    # document = text under Summary/Profile heading; model = synthesized (may not exist in PDF)
    summary_origin: Literal["document", "model"] = "model"
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: SkillsBlock = Field(default_factory=SkillsBlock)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    ats_score_baseline: Optional[float] = None
    leadership: list[str] = Field(default_factory=list)  # positions of responsibility
    extracurricular: list[str] = Field(default_factory=list)

    @field_validator("summary_origin", mode="before")
    @classmethod
    def _coerce_summary_origin(cls, v: Any) -> str:
        if v in ("document", "model"):
            return v
        if isinstance(v, str):
            low = v.lower().strip()
            if low in ("document", "model"):
                return low
        return "model"

    @field_validator("ats_score_baseline", mode="before")
    @classmethod
    def _coerce_ats_baseline(cls, v: Any) -> float | None:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


class ResumeOut(BaseModel):
    """Resume row; ``file_name`` is the original upload name (DB column ``file_url``)."""

    id: int
    user_id: int
    parsed_json: dict[str, Any]
    ats_baseline: Optional[float]
    active_template_id: str = ""
    created_at: datetime
    updated_at: datetime
    file_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ResumeUpdateIn(BaseModel):
    parsed_json: dict[str, Any]
    recalc_ats: bool = True


class GenerateSummaryIn(BaseModel):
    """Optional draft JSON to generate summary from (merged with stored resume; meta keys kept from server)."""

    parsed_json: Optional[dict[str, Any]] = None


class ResumeTemplateSelectIn(BaseModel):
    template_id: str = Field(min_length=1)


class JDAnalyzeIn(BaseModel):
    raw_jd: str


class JDAnalysisOut(BaseModel):
    id: int
    parsed_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class TailorStartIn(BaseModel):
    resume_id: int
    jd_analysis_id: int
    template_id: str = ""


class TailorSessionOut(BaseModel):
    id: int
    resume_id: int
    jd_id: Optional[int]
    output_resume_json: dict[str, Any]
    ats_score: Optional[float]
    template_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ATSScoreIn(BaseModel):
    resume_json: dict[str, Any]
    jd_keywords: list[str] = Field(default_factory=list)
    jd_analysis: Optional[dict[str, Any]] = None


class ATSScoreOut(BaseModel):
    overall: float
    dimensions: dict[str, float]
    suggestions: list[str]


class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: Optional[int] = None
    status: str = "saved"
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    job_id: int
    resume_id: Optional[int]
    status: str
    notes: str
    applied_at: Optional[datetime]
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    source: str
    title: str
    company: str
    location: str
    description: str
    salary_range: Optional[str]
    job_type: str
    remote: str
    skills: list[str]
    posted_at: datetime
    apply_url: Optional[str]
    match_score: Optional[float] = None
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    fit_rationale: Optional[str] = None  # LLM shortlist explanation when present

    model_config = {"from_attributes": True}


class JSearchSmartIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    resume_id: Optional[int] = None
    manual_query: str = ""
    country: str = ""
    work_type: str = "all"
    date_posted: str = "all"
    page: int = 1
    num_pages: int = 2


class JSearchSmartOut(BaseModel):
    jobs: list[JobOut]
    queries_used: list[str] = Field(default_factory=list)
    suggested_roles: list[str] = Field(default_factory=list)
    message: str = ""
    experience_years_used: Optional[int] = None
    experience_phrase: str = ""


class TemplateMeta(BaseModel):
    id: str
    name: str
    style: str
    best_for: str
    ats_score: int
    kind: str = "docx"
    source: str = "file"
    description: str = ""
    preview_variant: str = "clean"
    file_name: Optional[str] = None
