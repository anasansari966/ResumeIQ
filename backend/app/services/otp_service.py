from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.deps import hash_password
from app.models_db import EmailOtpCode, User

log = logging.getLogger(__name__)


def _hash_otp(email: str, otp: str) -> str:
    material = f"{email.lower().strip()}::{otp.strip()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_email(email: str, subject: str, body: str) -> bool:
    if not settings.smtp_host:
        return False
    try:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return True
    except Exception as e:
        log.warning("OTP email send failed: %s", e)
        return False


async def issue_registration_otp(session: AsyncSession, user: User) -> str:
    return await _issue_email_otp(
        session,
        user,
        purpose="register",
        subject="ResumeIQ verification code",
        body_prefix="Your OTP is",
    )


async def issue_password_reset_otp(session: AsyncSession, user: User) -> str:
    return await _issue_email_otp(
        session,
        user,
        purpose="reset_password",
        subject="ResumeIQ password reset code",
        body_prefix="Your password reset code is",
    )


async def _issue_email_otp(
    session: AsyncSession,
    user: User,
    *,
    purpose: str,
    subject: str,
    body_prefix: str,
) -> str:
    otp = generate_otp_code()
    now = datetime.utcnow()
    expires = now + timedelta(minutes=max(1, settings.otp_ttl_minutes))
    await session.exec(
        delete(EmailOtpCode).where(
            EmailOtpCode.user_id == user.id,
            EmailOtpCode.purpose == purpose,
            EmailOtpCode.consumed == False,  # noqa: E712
        )
    )
    row = EmailOtpCode(
        email=user.email.lower().strip(),
        user_id=user.id,
        code_hash=_hash_otp(user.email, otp),
        expires_at=expires,
        consumed=False,
        purpose=purpose,
    )
    session.add(row)
    await session.commit()
    body = f"{body_prefix} {otp}. It expires in {settings.otp_ttl_minutes} minutes."
    sent = _send_email(user.email, subject, body)
    if not sent:
        log.info("OTP for %s [%s] (dev/local): %s", user.email, purpose, otp)
    return otp


async def verify_registration_otp(session: AsyncSession, email: str, otp: str) -> User | None:
    pair = await _verify_email_otp(session, email, otp, purpose="register")
    if not pair:
        return None
    user, row = pair
    row.consumed = True
    user.email_verified = True
    session.add(row)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def reset_password_with_otp(session: AsyncSession, email: str, otp: str, new_password: str) -> User | None:
    pair = await _verify_email_otp(session, email, otp, purpose="reset_password")
    if not pair:
        return None
    user, row = pair
    row.consumed = True
    user.hashed_password = hash_password(new_password)
    user.email_verified = True
    session.add(row)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _verify_email_otp(
    session: AsyncSession,
    email: str,
    otp: str,
    *,
    purpose: str,
) -> tuple[User, EmailOtpCode] | None:
    em = email.lower().strip()
    result = await session.exec(select(User).where(User.email == em))
    user = result.first()
    if not user:
        return None
    result = await session.exec(
        select(EmailOtpCode)
        .where(
            EmailOtpCode.user_id == user.id,
            EmailOtpCode.email == em,
            EmailOtpCode.purpose == purpose,
            EmailOtpCode.consumed == False,  # noqa: E712
        )
        .order_by(EmailOtpCode.created_at.desc())
    )
    row = result.first()
    if not row:
        return None
    if row.expires_at < datetime.utcnow():
        return None
    if row.code_hash != _hash_otp(em, otp):
        return None
    return user, row
