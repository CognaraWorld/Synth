import hmac
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer

from app.config import get_settings
from app.models.credit_transaction import CreditTransaction
from app.models.database import DEFAULT_STARTER_CREDITS, User, get_db
from app.models.schemas import (
    LoginRequest,
    ServiceTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _validate_password(password: str) -> str | None:
    """Return an error message if password fails complexity requirements, None if OK.

    Enforces OWASP password guidelines (A07:2021 - Identification and
    Authentication Failures): minimum length, mixed case, and digits.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one digit"
    return None


def _get_jwt_secret() -> str:
    if settings.secret_key in {"", "change-me-in-production"}:
        raise RuntimeError(
            "Authentication is not configured. Set BACKEND_SECRET_KEY before issuing tokens."
        )
    return settings.secret_key


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"iat": datetime.now(timezone.utc), "exp": expire})
    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=settings.algorithm)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_uuid = UUID(user_id)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        )

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    if user_data.provider != "email":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only supports email/password registration.",
        )
    password = (user_data.password or "").strip()
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required for email/password registration.",
        )
    password_error = _validate_password(password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=user_data.email,
        name=user_data.name,
        hashed_password=pwd_context.hash(password),
        provider=user_data.provider,
    )
    db.add(user)
    await db.flush()

    if user.credits:
        db.add(
            CreditTransaction(
                user_id=user.id,
                amount=user.credits,
                balance_after=user.credits,
                transaction_type="free_credit",
                description="Starter credits granted on registration",
            )
        )

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        token = create_access_token({"sub": str(user.id)})
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        )
    return TokenResponse(access_token=token)


@router.post("/service-token", response_model=TokenResponse)
async def service_token(req: ServiceTokenRequest, db: AsyncSession = Depends(get_db)):
    """Service-to-service token exchange for BFF (NextAuth dashboard)."""
    expected = settings.service_secret
    if not expected or not hmac.compare_digest(req.service_secret, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service secret")

    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=req.email, name=req.name, provider="google")
        db.add(user)
        await db.flush()

        db.add(
            CreditTransaction(
                user_id=user.id,
                amount=DEFAULT_STARTER_CREDITS,
                balance_after=DEFAULT_STARTER_CREDITS,
                transaction_type="free_credit",
                description="Starter credits on service registration",
            )
        )

        await db.commit()
        await db.refresh(user)

    try:
        token = create_access_token({"sub": str(user.id)})
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        )

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
