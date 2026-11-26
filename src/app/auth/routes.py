import os
import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.database import get_db
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    MessageResponse
)
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user."""

    email = request.email.lower()

    # Check whether the email is already registered.
    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    # Hash the password before saving it.
    user = User(
        email=email,
        hashed_password=hash_password(request.password),
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    return user



@router.post("/login", response_model=TokenResponse)
def login_user(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate a user and issue tokens."""

    email = request.email.lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # Use the same error for unknown email and wrong password.
    if not user or not verify_password(
        request.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    # Generate tokens.
    access_token = create_access_token(user.id)

    refresh_token, expires_at = create_refresh_token(user.id)

    # Store only the hash of the refresh token.
    refresh_session = RefreshSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at.replace(tzinfo=None),
    )

    db.add(refresh_session)
    db.commit()

    # Store refresh token as an HttpOnly cookie.
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/auth",
    )

    return TokenResponse(
        access_token=access_token,
    )




@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Rotate the refresh token and issue a new access token."""

    old_refresh_token = request.cookies.get("refresh_token")

    if not old_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing.",
        )

    # 1. Verify the JWT signature and expiration.
    try:
        payload = decode_token(old_refresh_token)

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type.")

        user_id = int(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    # 2. Find and lock the existing refresh session.
    old_token_hash = hash_refresh_token(old_refresh_token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    old_session = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.token_hash == old_token_hash,
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        )
        .with_for_update()
        .first()
    )

    if not old_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is invalid or revoked.",
        )

    # 3. Verify that the account still exists and is active.
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is unavailable.",
        )

    # 4. Revoke the old session.
    old_session.revoked_at = now

    # 5. Generate replacement tokens.
    new_access_token = create_access_token(user.id)

    new_refresh_token, expires_at = create_refresh_token(user.id)

    new_session = RefreshSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh_token),
        expires_at=expires_at.replace(tzinfo=None),
    )

    db.add(new_session)

    # Revoke old session and save new session atomically.
    db.commit()

    # 6. Send the new refresh token as an HttpOnly cookie.
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/auth",
    )

    return TokenResponse(
        access_token=new_access_token,
    )




@router.post("/logout", response_model=MessageResponse)
def logout_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Revoke the current refresh session and clear its cookie."""

    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        try:
            payload = decode_token(refresh_token)

            if payload.get("type") == "refresh":
                token_hash = hash_refresh_token(refresh_token)

                session = (
                    db.query(RefreshSession)
                    .filter(
                        RefreshSession.token_hash == token_hash,
                        RefreshSession.revoked_at.is_(None),
                    )
                    .with_for_update()
                    .first()
                )

                if session:
                    session.revoked_at = (
                        datetime.now(timezone.utc).replace(tzinfo=None)
                    )
                    db.commit()

        except jwt.InvalidTokenError:
            # Even if the token is invalid or expired,
            # we should still clear the browser cookie.
            db.rollback()

    response.delete_cookie(
        key="refresh_token",
        path="/auth",
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
    )

    return MessageResponse(
        message="Logged out successfully."
    )


@router.get("/me", response_model=UserResponse)
def get_logged_in_user(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user."""
    return current_user