import hmac
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer

from app.config import get_settings
from app.core.rate_limiter import check_named_limit
from app.core.ws_tickets import issue_ticket
from app.models.credit_transaction import CreditTransaction
from app.models.database import DEFAULT_STARTER_CREDITS, User, get_db
from app.models.schemas import (
    LoginRequest,
    ServiceTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    WebSocketTicketResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# Any deployment that still has the repo-shipped default is effectively
# unauthenticated — reject at the endpoint level even before constant-time
# comparison runs.
_INSECURE_SERVICE_SECRETS = frozenset(
    {"", "cognara-service-secret-dev", "change-me", "change-me-in-production"}
)


def _client_ip(request: Request) -> str:
    """Best-effort client IP extraction for rate-limit keys.

    Prefers ``X-Forwarded-For`` (first address) when running behind a
    reverse proxy, falls back to the direct socket peer. Ignores anything
    unparseable so a missing header never yields a blank key.
    """
    fwd = request.headers.get("x-forwarded-for") or ""
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    client = request.client
    if client and client.host:
        return client.host
    return "unknown"


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
    to_encode.update(
        {
            "iat": datetime.now(timezone.utc),
            "exp": expire,
            # jti enables future token revocation lists without reissuing the whole secret.
            "jti": uuid4().hex,
        }
    )
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
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[settings.algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_uuid = UUID(user_id)
    except (InvalidTokenError, ValueError, TypeError):
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
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await check_named_limit("register", _client_ip(request))
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
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await check_named_limit("login", _client_ip(request))
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
async def service_token(
    req: ServiceTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Service-to-service token exchange for BFF (NextAuth dashboard)."""
    await check_named_limit("service-token", _client_ip(request))

    expected = settings.service_secret
    # Refuse to issue tokens when the deployment still ships with the
    # default secret or leaves BACKEND_SERVICE_SECRET unset. This closes
    # the P0 "default secret = account takeover" finding from the audit.
    if expected in _INSECURE_SERVICE_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service auth is not configured on this deployment.",
        )
    if not hmac.compare_digest(req.service_secret, expected):
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


@router.post("/ws-ticket", response_model=WebSocketTicketResponse)
async def issue_ws_ticket(
    current_user: User = Depends(get_current_user),
) -> WebSocketTicketResponse:
    """Mint a short-lived single-use ticket for the WebSocket endpoint.

    The browser calls this with its normal bearer token (through the BFF),
    gets back an opaque ticket, and uses the ticket in the WebSocket URL
    instead of the full JWT. Tickets expire after 60 seconds and are
    consumed on first use — see ``app.core.ws_tickets`` for rationale.
    """
    ticket, expires_in = issue_ticket(current_user.id)
    return WebSocketTicketResponse(ticket=ticket, expires_in=expires_in)
