"""
Auth dependency for FastAPI route handlers.

Real Supabase JWT verification. Supabase Auth issues HS256 JWTs signed with the
project's JWT secret; this module verifies that signature server-side on every
protected request, extracts the user id (sub) and email, and hands a CurrentUser
to the route layer.

Security invariants:
  - The JWT secret (settings.supabase_jwt_secret) is NEVER logged or returned in
    any response. A misconfigured secret yields a generic 500, not a leak.
  - skip_auth is honoured FIRST so the local-dev test path is unambiguous. The
    production path has NO env fallback — a missing secret is a hard 500.
  - Expired tokens get a distinct message from otherwise-invalid tokens so the
    client can prompt re-login rather than treat it as tampering.
  - audience="authenticated" matches the aud claim Supabase stamps on every token,
    rejecting tokens minted for other audiences.

The function signature (token: str, return: CurrentUser) is stable. Callers import
only `get_current_user` and `CurrentUser` from this module.
"""

import uuid
from dataclasses import dataclass

import jwt  # PyJWT — already in requirements.txt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

# ---------------------------------------------------------------------------
# OAuth2 scheme — tokenUrl is the endpoint that issues tokens.
# FastAPI uses this to generate the OpenAPI security scheme; the actual token
# validation logic lives in get_current_user below.
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---------------------------------------------------------------------------
# CurrentUser: the object injected into every authenticated route handler.
# Kept as a plain dataclass so it has zero ORM coupling — the auth layer
# constructs it from the validated JWT claims and hands it to the route layer.
# ---------------------------------------------------------------------------
@dataclass
class CurrentUser:
    """Minimal user context extracted from a verified JWT."""

    id: uuid.UUID
    email: str


# ---------------------------------------------------------------------------
# Hardcoded test user for SKIP_AUTH=true local development only.
# These values are intentionally non-secret: they cannot authenticate against
# any real system. They are never used when SKIP_AUTH is absent or false, and
# main.py's lifespan refuses to start if SKIP_AUTH is set in production.
# ---------------------------------------------------------------------------
_DEV_USER = CurrentUser(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    email="dev@nutritrack.local",
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
    """
    FastAPI dependency — resolves the authenticated user for the current request.

    SKIP_AUTH=true  → returns the hardcoded _DEV_USER (local dev only).
    Otherwise       → verifies the Supabase-issued HS256 JWT and returns the user.

    Args:
        token: Bearer token extracted from the Authorization header by
               OAuth2PasswordBearer.

    Returns:
        CurrentUser with the authenticated user's id and email.

    Raises:
        HTTPException 401: token missing, expired, malformed, or claims invalid.
        HTTPException 500: server JWT secret not configured (never leaks the secret).
    """
    if settings.skip_auth:
        return _DEV_USER

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증에 실패했습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Production path: no env fallback. A missing secret is a hard server error,
    # never a silent bypass. The secret value itself is never included in the
    # response — only a generic message.
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 인증 설정이 없습니다.",
        )

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        # Expired ≠ tampered: prompt the client to re-login.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 만료됐습니다. 다시 로그인해주세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # Bad signature, wrong audience, malformed token — all opaque to the client.
        raise credentials_exception

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise credentials_exception

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    return CurrentUser(id=user_id, email=email)
