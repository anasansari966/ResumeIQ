from pathlib import Path
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env (and optional repo-root .env) — not dependent on cwd.
# Order matters: pydantic-settings applies later files on top of earlier ones, so backend/.env must be LAST
# so repo-root `.env` cannot override SERPAPI_KEY / DB with empty values.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILES: tuple[str, ...] = tuple(
    str(p)
    for p in (
        _BACKEND_ROOT.parent / ".env",
        _BACKEND_ROOT / ".env",
    )
    if p.is_file()
) or (str(_BACKEND_ROOT / ".env"),)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Preferred explicit DSN (works with MySQL Workbench local server):
    # DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/resumeiq
    # If empty, we can auto-build MySQL DSN from mysql_* fields below.
    database_url: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "resumeiq"
    use_mysql: bool = False
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    openai_parse_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("OPENAI_MODEL", "OPENAI_PARSE_MODEL", "openai_parse_model"),
    )
    # Legacy RapidAPI JSearch (unused when SerpAPI is configured)
    rapidapi_key: str = Field(default="", validation_alias=AliasChoices("RAPIDAPI_KEY", "rapidapi_key"))
    # SerpAPI Google Jobs — https://serpapi.com/manage-api-key (each unique search counts toward plan; cache hits are free ~1h)
    serpapi_key: str = Field(default="", validation_alias=AliasChoices("SERPAPI_KEY", "serpapi_key"))
    serpapi_max_queries_per_search: int = Field(
        default=2,
        validation_alias=AliasChoices("SERPAPI_MAX_QUERIES_PER_SEARCH"),
    )
    serpapi_max_pages_per_query: int = Field(
        default=1,
        validation_alias=AliasChoices("SERPAPI_MAX_PAGES_PER_QUERY"),
    )
    serpapi_dry_run: bool = Field(
        default=False,
        validation_alias=AliasChoices("SERPAPI_DRY_RUN", "serpapi_dry_run"),
    )
    # Google organic search (same SERPAPI_KEY) for ATS / company career apply links — separate credit use from JobSpy.
    serpapi_web_jobs_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("SERPAPI_WEB_JOBS_ENABLED", "serpapi_web_jobs_enabled"),
    )
    serpapi_web_jobs_max_roles: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias=AliasChoices("SERPAPI_WEB_JOBS_MAX_ROLES", "serpapi_web_jobs_max_roles"),
    )
    serpapi_web_jobs_max_hits: int = Field(
        default=12,
        ge=1,
        le=30,
        validation_alias=AliasChoices("SERPAPI_WEB_JOBS_MAX_HITS", "serpapi_web_jobs_max_hits"),
    )
    linkedin_jobspy_max_queries: int = Field(
        default=6,
        ge=1,
        le=8,
        validation_alias=AliasChoices("LINKEDIN_JOBSPY_MAX_QUERIES", "linkedin_jobspy_max_queries"),
    )
    linkedin_jobspy_results_per_query: int = Field(
        default=16,
        validation_alias=AliasChoices("LINKEDIN_JOBSPY_RESULTS_PER_QUERY", "linkedin_jobspy_results_per_query"),
    )
    # LinkedIn list cards often have no body text; fetching each job page is slower but fills the JD panel.
    jobspy_linkedin_fetch_descriptions: bool = Field(
        default=True,
        validation_alias=AliasChoices("JOBSPY_LINKEDIN_FETCH_DESCRIPTIONS", "jobspy_linkedin_fetch_descriptions"),
    )
    # LinkedIn guest search often returns HTTP 500 for very large f_TPR (e.g. 8760h → r31536000).
    # At or above this many hours we omit the time filter so LinkedIn returns its default any-time feed.
    jobspy_linkedin_omit_time_filter_hours_gte: int = Field(
        default=7200,
        ge=24,
        le=8760,
        validation_alias=AliasChoices(
            "JOBSPY_LINKEDIN_OMIT_TIME_FILTER_HOURS_GTE",
            "jobspy_linkedin_omit_time_filter_hours_gte",
        ),
    )
    # Comma-separated JobSpy boards. Default (empty): linkedin,indeed,google. Optional: zip_recruiter,bayt,bdjobs
    jobspy_sites: str = Field(
        default="",
        validation_alias=AliasChoices("JOBSPY_SITES", "jobspy_sites"),
    )
    jobspy_shortlist_llm_pool: int = Field(
        default=50,
        ge=5,
        le=80,
        validation_alias=AliasChoices("JOBSPY_SHORTLIST_LLM_POOL", "jobspy_shortlist_llm_pool"),
    )
    jobspy_shortlist_max_results: int = Field(
        default=28,
        ge=3,
        le=55,
        validation_alias=AliasChoices("JOBSPY_SHORTLIST_MAX_RESULTS", "jobspy_shortlist_max_results"),
    )
    templates_dir: str = ""
    resume_template_docx: str = "Document 3.docx"
    # OTP email (optional; OTP always logged when SMTP disabled)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    otp_ttl_minutes: int = 15

    @field_validator("openai_api_key", "serpapi_key", "rapidapi_key", mode="before")
    @classmethod
    def _strip_api_secrets(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()


settings = Settings()


def resolved_database_url() -> str:
    explicit = (settings.database_url or "").strip()
    if explicit:
        return explicit
    if settings.use_mysql:
        # Encode user/password so values like "pass@word" do not break the URL.
        u = quote_plus(settings.mysql_user or "", safe="")
        p = quote_plus(settings.mysql_password or "", safe="")
        return (
            f"mysql+aiomysql://{u}:{p}"
            f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}"
        )
    return "sqlite+aiosqlite:///./resumeiq.db"
