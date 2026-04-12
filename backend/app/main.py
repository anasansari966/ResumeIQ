"""FastAPI app. Imports assume `backend/` is on sys.path (package `app`)."""
from __future__ import annotations

import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from app.config import settings
from app.database import async_session_factory, engine, init_db
from app.models_db import Application, JDAnalysis, JobListing, Resume, TailoringSession, User  # noqa: F401
from app.routers import applications as applications_rt
from app.routers import ats as ats_rt
from app.routers import auth as auth_rt
from app.routers import jd as jd_rt
from app.routers import jobs as jobs_rt
from app.routers import resumes as resumes_rt
from app.routers import tailor as tailor_rt
from app.routers import templates_market_rt
from app.services.job_seeds import seed_jobs
from app.services.template_catalog import sync_template_catalog


async def seed_job_listings():
    async with async_session_factory() as session:
        res = await session.exec(select(JobListing))
        if not res.all():
            for row in seed_jobs():
                session.add(JobListing(**row))
            await session.commit()


async def seed_template_catalog():
    async with async_session_factory() as session:
        await sync_template_catalog(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_job_listings()
    await seed_template_catalog()
    yield
    await engine.dispose()


app = FastAPI(title="ResumeIQ API", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_rt.router)
app.include_router(resumes_rt.router)
app.include_router(jd_rt.router)
app.include_router(tailor_rt.router)
app.include_router(ats_rt.router)
app.include_router(jobs_rt.router)
app.include_router(applications_rt.router)
app.include_router(templates_market_rt.router)

_resumeiq_root = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST = _resumeiq_root / "frontend" / "dist"


def _mount_resumeiq_ui(application: FastAPI) -> None:
    """Serve Vite production build at /resumeiq/ when frontend/dist exists."""
    dist = FRONTEND_DIST
    index = dist / "index.html"
    assets_dir = dist / "assets"
    if not index.is_file():
        return

    @application.get("/resumeiq", include_in_schema=False)
    async def resumeiq_redirect_slash(request: Request) -> RedirectResponse:
        qs = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(url=f"/resumeiq/{qs}")

    @application.get("/resumeiq/", include_in_schema=False)
    async def resumeiq_shell() -> FileResponse:
        return FileResponse(index)

    if assets_dir.is_dir():
        application.mount(
            "/resumeiq/assets",
            StaticFiles(directory=assets_dir),
            name="resumeiq_assets",
        )

    @application.get("/resumeiq/{full_path:path}", include_in_schema=False)
    async def resumeiq_spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("assets/"):
            raise HTTPException(status_code=404)
        return FileResponse(index)

    @application.get("/", include_in_schema=False)
    async def root_redirect_resumeiq(request: Request) -> RedirectResponse:
        qs = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(url=f"/resumeiq/{qs}")


_mount_resumeiq_ui(app)


@app.get("/health")
async def health():
    return {"status": "ok"}
