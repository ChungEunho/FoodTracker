"""
Auth dependency for FastAPI route handlers.

Supabase Auth now issues ES256 JWTs (asymmetric ECDSA, not HS256). Verification
uses the Supabase JWKS endpoint so the signing key is never stored in env vars.

Security invariants:
  - The JWKS client is lazy-initialised and cached at module level (one fetch per
    process, re-fetched automatically when a key-id is not found — handles key
    rotation without a redeploy).
  - skip_auth is honoured FIRST so the local-dev test path is unambiguous.
  - Expired tokens get a distinct message from otherwise-invalid tokens.
  - audience="authenticated" matches the aud claim Supabase stamps on every token.

The function signature (token: str, return: CurrentUser) is stable. Callers import
only `get_current_user` and `CurrentUser` from this module.
"""

import uuid
from dataclasses import dataclass

import jwt  # PyJWT — already in requirements.txt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

# ---------------------------------------------------------------------------
# OAuth2 scheme — tokenUrl is the endpoint that issues tokens.
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# ---------------------------------------------------------------------------
# JWKS client — lazy-initialised on first request, then cached.
# PyJWKClient fetches the public keys from Supabase and caches them in memory.
# ---------------------------------------------------------------------------
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


# ---------------------------------------------------------------------------
# CurrentUser: the object injected into every authenticated route handler.
# ---------------------------------------------------------------------------
@dataclass
class CurrentUser:
    """Minimal user context extracted from a verified JWT."""

    id: uuid.UUID
    email: str


# ---------------------------------------------------------------------------
# Hardcoded test user for SKIP_AUTH=true local development only.
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
    Otherwise       → verifies the Supabase-issued ES256 JWT via JWKS and returns
                      the user.

    Raises:
        HTTPException 401: token missing, expired, malformed, or claims invalid.
        HTTPException 500: supabase_url not configured or JWKS unreachable.
    """
    if settings.skip_auth:
        return _DEV_USER

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증에 실패했습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 인증 설정이 없습니다.",
        )

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 만료됐습니다. 다시 로그인해주세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인증 서버에 연결할 수 없습니다.",
        )

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise credentials_exception

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    return CurrentUser(id=user_id, email=email)
