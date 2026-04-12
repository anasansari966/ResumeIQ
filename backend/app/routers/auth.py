from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.database import get_session
from app.deps import CurrentUser, create_token, hash_password, verify_password
from app.models_db import User
from app.schemas import (
    ActionMessageOut,
    ForgotPasswordIn,
    RegisterOut,
    ResendOtpIn,
    ResetPasswordIn,
    Token,
    UserCreate,
    UserPublic,
    VerifyOtpIn,
)
from app.services.otp_service import (
    issue_password_reset_otp,
    issue_registration_otp,
    reset_password_with_otp,
    verify_registration_otp,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=RegisterOut)
async def register(body: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]):
    existing = await session.exec(select(User).where(User.email == body.email))
    if existing.first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=body.email.lower().strip(), hashed_password=hash_password(body.password), name=body.name or "")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    otp = await issue_registration_otp(session, user)
    return RegisterOut(
        user_id=user.id,
        email=user.email,
        dev_otp=otp if not (settings.smtp_host or "").strip() else None,
    )


@router.post("/login", response_model=Token)
async def login(body: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]):
    result = await session.exec(select(User).where(User.email == body.email.lower().strip()))
    user = result.first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Verify OTP to continue.")
    return Token(access_token=create_token(str(user.id)))


@router.post("/verify-otp", response_model=Token)
async def verify_otp(body: VerifyOtpIn, session: Annotated[AsyncSession, Depends(get_session)]):
    user = await verify_registration_otp(session, body.email, body.otp)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    return Token(access_token=create_token(str(user.id)))


@router.post("/resend-otp", response_model=RegisterOut)
async def resend_otp(body: ResendOtpIn, session: Annotated[AsyncSession, Depends(get_session)]):
    result = await session.exec(select(User).where(User.email == body.email.lower().strip()))
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    otp = await issue_registration_otp(session, user)
    return RegisterOut(
        user_id=user.id,
        email=user.email,
        dev_otp=otp if not (settings.smtp_host or "").strip() else None,
    )


@router.post("/forgot-password", response_model=ActionMessageOut)
async def forgot_password(body: ForgotPasswordIn, session: Annotated[AsyncSession, Depends(get_session)]):
    em = body.email.lower().strip()
    result = await session.exec(select(User).where(User.email == em))
    user = result.first()
    dev_otp = None
    if user:
        otp = await issue_password_reset_otp(session, user)
        dev_otp = otp if not (settings.smtp_host or "").strip() else None
    return ActionMessageOut(
        message="If an account exists for that email, a password reset code has been sent.",
        dev_otp=dev_otp,
    )


@router.post("/reset-password", response_model=Token)
async def reset_password(body: ResetPasswordIn, session: Annotated[AsyncSession, Depends(get_session)]):
    user = await reset_password_with_otp(session, body.email, body.otp, body.new_password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    return Token(access_token=create_token(str(user.id)))


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser):
    return UserPublic(id=user.id, email=user.email, name=user.name, plan=user.plan)
