"""One-shot: init DB and seed demo users. Run from backend/: python scripts/seed_demo_users.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import async_session_factory, init_db
from app.services.seed_users import SEED_ACCOUNTS, seed_demo_users


async def main() -> None:
    await init_db()
    async with async_session_factory() as session:
        result = await seed_demo_users(session)
    print("Seed result:", result)
    for row in SEED_ACCOUNTS:
        print(f"  {row['role']:12} {row['email']} / {row['password']}")


if __name__ == "__main__":
    asyncio.run(main())
