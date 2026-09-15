"""Drop and recreate the app database (MySQL) or delete the SQLite file. Run from repo: python scripts/reset_db.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import quote_plus

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import resolved_database_url, settings


def _sqlite_file() -> Path | None:
    url = resolved_database_url()
    if "sqlite" not in url:
        return None
    rest = url.split("sqlite+aiosqlite:///", 1)[-1]
    if rest.startswith("./"):
        return (BACKEND_ROOT / rest[2:]).resolve()
    if rest.startswith("/"):
        return Path(rest)
    return (BACKEND_ROOT / rest).resolve()


async def _reset_mysql() -> None:
    u = quote_plus(settings.mysql_user or "")
    p = quote_plus(settings.mysql_password or "")
    admin_url = f"mysql+aiomysql://{u}:{p}@{settings.mysql_host}:{settings.mysql_port}/mysql"
    db = settings.mysql_db
    engine = create_async_engine(admin_url)
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS `{db}`"))
        await conn.execute(
            text(f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"),
        )
    await engine.dispose()
    print(f"MySQL database reset: {db}")


def main() -> None:
    if settings.use_mysql:
        asyncio.run(_reset_mysql())
        return
    path = _sqlite_file()
    if path and path.is_file():
        path.unlink()
        print(f"Removed SQLite file: {path}")
    elif path:
        print(f"No SQLite file at {path} (already clean).")
    else:
        print("Unknown database URL; nothing done.")


if __name__ == "__main__":
    main()
