"""Seed demo login accounts (verified, ready to use). Idempotent upsert by email."""
from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.deps import hash_password
from app.models_db import User

# Local/dev credentials — change in production.
SEED_ACCOUNTS: tuple[dict[str, str], ...] = (
    {
        "email": "admin@resumeiq.dev",
        "password": "Admin@12345",
        "name": "Super Admin",
        "plan": "pro",
        "role": "superadmin",
    },
    {
        "email": "user@resumeiq.dev",
        "password": "User@12345",
        "name": "Demo User",
        "plan": "free",
        "role": "user",
    },
)


async def seed_demo_users(session: AsyncSession) -> list[str]:
    """Ensure seeded accounts exist with known passwords and verified email."""
    touched: list[str] = []
    with session.no_autoflush:
        for row in SEED_ACCOUNTS:
            email = row["email"].lower().strip()
            result = await session.exec(select(User).where(User.email == email))
            user = result.first()
            if user is None:
                user = User(
                    email=email,
                    hashed_password=hash_password(row["password"]),
                    name=row["name"],
                    plan=row["plan"],
                    role=row["role"],
                    email_verified=True,
                )
                session.add(user)
                touched.append(f"created:{email}")
            else:
                user.hashed_password = hash_password(row["password"])
                user.name = row["name"]
                user.plan = row["plan"]
                user.role = row["role"]
                user.email_verified = True
                session.add(user)
                touched.append(f"updated:{email}")
    if touched:
        await session.commit()
    return touched
