from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.core.config import settings
from app.db.database import get_session
from app.dependencies.auth import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.course import Course, CourseStatus
from app.schemas.errors import ApiError
from app.schemas.user import User, UserRead

ph = PasswordHasher()
auth_router = APIRouter()

# Finding R15, decided 18 Aug: every new account gets one course so that the
# first run is not a dead end. The names live here rather than inline because
# the course listing UI has to be able to recognise this row.
UNSORTED_COURSE_CODE = "UNSORTED"
UNSORTED_COURSE_NAME = "Unsorted"


@auth_router.get(
    "/me",
    response_model=UserRead,
    responses={401: {"model": ApiError, "description": "Missing, invalid or expired access token"}},
)
async def get_me(
    payload: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Returns the current logged-in user's profile"""

    # get_current_user returns the decoded JWT payload, not a User row: the token
    # carries sub/name/email but neither id nor created_at, so UserRead cannot be
    # built from it. Look the user up the same way refresh_session does.
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or tampered token"},
        )

    statement = select(User).where(col(User.id) == user_id)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User account no longer exists"},
        )

    return user


@auth_router.post("/logout")
async def logout(response: Response, _=Depends(get_current_user)):
    """Logs out the user by clearing the HttpOnly refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
    )
    return {"status": "ok"}


@auth_router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ApiError, "description": "Invalid or expired refresh token"}},
)
async def refresh_session(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
):
    """Refreshes an expired access token using HttpOnly refresh token cookie."""

    # get JWT encoded refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NO_REFRESH_TOKEN", "message": "Refresh token is missing from cookies"},
        )

    # decode jwt payload to get user ID
    try:
        payload = jwt.decode(
            refresh_token, settings.REFRESH_TOKEN_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "Invalid or tampered refresh token",
                },
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "REFRESH_TOKEN_EXPIRED",
                "message": "Refresh token has expired. Please log in again",
            },
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "Invalid or tampered refresh token",
            },
        )

    # ensure user ID exist in database
    # this ensures user hasn't deleted their account, banned, disabled and user's data is up to date
    statement = select(User).where(col(User.id) == user_id)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User account no longer exists"},
        )

    # issue new access token and refresh token in cookie
    new_access_token = create_access_token(user, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_refresh_token = create_refresh_token(user, settings.REFRESH_TOKEN_EXPIRE_DAYS)

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,  # JS cannot read cookie, prevents XSS attack
        samesite="lax",  # CSRF protection
        secure=settings.AUTH_COOKIE_SECURE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )

    return TokenResponse(
        access_token=new_access_token, token_type="bearer", user=UserRead.model_validate(user)
    )


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ApiError, "description": "Invalid email or password"}},
)
async def login(
    body: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)
):
    """Authenticates a user and returns a JWT access token."""

    # authenticate user
    statement = select(User).where(col(User.email) == body.email)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Email or password incorrect"},
        )

    try:
        ph.verify(user.hashed_password, body.password.encode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Email or password incorrect"},
        )

    # issue access token and refersh token in cookie
    access_token = create_access_token(user, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_refresh_token(user, settings.REFRESH_TOKEN_EXPIRE_DAYS)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # JS cannot read cookie, prevents XSS attack
        samesite="lax",  # CSRF protection
        secure=settings.AUTH_COOKIE_SECURE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )

    return TokenResponse(
        access_token=access_token, token_type="bearer", user=UserRead.model_validate(user)
    )


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    responses={400: {"model": ApiError, "description": "Email already exists"}},
)
async def register(
    body: RegisterRequest, response: Response, session: AsyncSession = Depends(get_session)
):
    """Registers a new user account."""

    statement = select(User).where(col(User.email) == body.email)
    result = await session.execute(statement)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_EXISTS", "message": "A user with this email already exists"},
        )

    # hash password and create user account
    bytes = body.password.encode("utf-8")
    hashed_password = ph.hash(bytes)

    # The id is minted here rather than left to `default_factory` so the default
    # course can reference it before either row is flushed. Both INSERTs go in one
    # transaction: an account that committed without its course would be unable to
    # open a conversation at all, which is the whole of finding R15.
    user_id = uuid4()
    user = User(
        id=user_id,
        hashed_password=hashed_password,
        email=body.email,
        display_name=body.display_name,
    )
    session.add(user)
    await session.flush()
    session.add(build_unsorted_course(user_id))
    await session.commit()
    await session.refresh(user)

    # create token
    token = create_access_token(user, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_refresh_token(user, settings.REFRESH_TOKEN_EXPIRE_DAYS)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # JS cannot read cookie, prevents XSS attack
        samesite="lax",  # CSRF protection
        secure=settings.AUTH_COOKIE_SECURE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )

    return TokenResponse(
        access_token=token, token_type="bearer", user=UserRead.model_validate(user)
    )


def create_refresh_token(user: User, expires_in_days: int) -> str:
    now = datetime.now(UTC)

    payload = {"sub": str(user.id), "iat": now, "exp": now + timedelta(days=expires_in_days)}

    token = jwt.encode(payload, settings.REFRESH_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def create_access_token(user: User, expires_in_minutes: int) -> str:
    now = datetime.now(UTC)

    payload = {
        "sub": str(user.id),
        "name": user.display_name,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
    }

    token = jwt.encode(payload, settings.ACCESS_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def build_unsorted_course(user_id: UUID) -> Course:
    """The default course every account starts with -- finding R15, decided 18 Aug.

    `CONVERSATION.course_id` is NOT NULL and, since finding R1 removed
    `CONVERSATION.user_id`, it is the only path from a conversation to its owner.
    So an account holding no course cannot open a chat. Creating this row at signup
    removes that dead end without making the column nullable.

    `year` and `sem` are 0 rather than the calendar year on purpose. They mark the
    row as a placeholder rather than a real enrolment, and they keep it stable:
    under finding R17's `UNIQUE (user_id, code, year, sem)` an account holds exactly
    one Unsorted course however long it lives.
    """
    return Course(
        user_id=user_id,
        code=UNSORTED_COURSE_CODE,
        name=UNSORTED_COURSE_NAME,
        year=0,
        sem=0,
        # `Course.status` is free text: the column was ratified on 27 Jul but its
        # value set never was. "active" is the obvious reading and is written here
        # without claiming to settle it.
        status=CourseStatus.ACTIVE,
    )
