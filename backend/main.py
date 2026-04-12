"""Entry shim: run from `backend/` with `uvicorn main:app` (same as `uvicorn app.main:app`)."""

from app.main import app

__all__ = ["app"]
