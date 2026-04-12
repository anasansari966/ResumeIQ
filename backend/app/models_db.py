from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    name: str = ""
    plan: str = Field(default="free")
    email_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None


class EmailOtpCode(SQLModel, table=True):
    """One-time code for email verification after registration."""

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    code_hash: str
    expires_at: datetime
    consumed: bool = Field(default=False)
    purpose: str = Field(default="register")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Resume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    file_url: Optional[str] = None
    parsed_json: dict = Field(sa_column=Column(JSON), default_factory=dict)
    ats_baseline: Optional[float] = None
    active_template_id: str = ""
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted: bool = False


class JDAnalysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # VARCHAR(255) on MySQL is too small for pasted JDs; TEXT/MEDIUMTEXT via migration.
    raw_jd: str = Field(sa_column=Column(Text), default="")
    parsed_json: dict = Field(sa_column=Column(JSON), default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TailoringSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id", index=True)
    jd_id: Optional[int] = Field(default=None, foreign_key="jdanalysis.id")
    output_resume_json: dict = Field(sa_column=Column(JSON), default_factory=dict)
    pdf_path: Optional[str] = None
    ats_score: Optional[float] = None
    template_id: str = ""
    status: str = Field(default="draft")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobListing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    external_id: str = Field(index=True)
    title: str
    company: str
    location: str = ""
    description: str = Field(sa_column=Column(Text), default="")
    salary_range: Optional[str] = None
    job_type: str = "full-time"
    remote: str = "hybrid"
    skills: list = Field(sa_column=Column(JSON), default_factory=list)
    posted_at: datetime = Field(default_factory=datetime.utcnow)
    apply_url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    job_id: int = Field(foreign_key="joblisting.id", index=True)
    resume_id: Optional[int] = Field(default=None, foreign_key="resume.id")
    status: str = Field(default="saved")
    notes: str = ""
    applied_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TemplateCatalog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    style: str = "LaTeX"
    best_for: str = ""
    ats_score: int = 90
    kind: str = "latex"
    source: str = "builtin"
    description: str = ""
    preview_variant: str = "clean"
    preview_asset: Optional[str] = None
    entry_path: Optional[str] = None
    folder_path: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeTemplateSelection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    template_id: str = Field(index=True)
    template_name: str = ""
    source: str = "unknown"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApplicationEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    from_status: str = ""
    to_status: str = ""
    note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
