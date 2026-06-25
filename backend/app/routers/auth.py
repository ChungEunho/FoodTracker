"""
Auth router — server-side session invalidation.

Single endpoint: POST /auth/logout (mounted under /api/v1 in main.py).

Supabase Auth owns credential storage and token issuance. The frontend handles
sign-up / login / signOut directly against Supabase. This backend endpoint exists
solely to perform the *server-side* invalidation that signOut() alone cannot:
revoking refresh tokens for ALL of the user's sessions (other devices, other tabs
holding older tokens), via the Supabase Admin API.

IDOR audit (last reviewed 2026-06-25):
  | Endpoint          | User-owned resource | Ownership check                          |
  |-------------------|---------------------|------------------------------------------|
  | POST /auth/logout | User sessions       | current_user.id from verified JWT only   |
  The target user id comes from the verified bearer token (get_current_user),
  never from the request body or a path param — one user cannot log out another.
  No id is accepted from the client, so there is no IDOR vector.
"""

import logging

import httpx
from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, get_current_user
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/logout", status_code=200)
async def logout(current_user: CurrentUser = Depends(get_current_user)):
    """
    Server-side session invalidation via the Supabase Admin API.

    Called BY the frontend AFTER supabase.auth.signOut() has cleared the client's
    local session. signOut() revokes the specific refresh token used in that
    browser; this endpoint additionally revokes ALL refresh tokens for the user so
    that other devices/tabs holding older tokens are invalidated too.

    Requires a valid bearer token (get_current_user) — only the authenticated user
    can trigger logout of their own sessions; current_user.id comes from the
    verified JWT, never from the request body, so one user cannot log out another.

    Best-effort: if the Admin API errors or Supabase is unreachable, the client has
    already cleared its local session (the critical step), so we still return 200.
    If Supabase is not configured (local dev), we skip gracefully.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        # Local dev without Supabase — skip gracefully.
        return {"message": "로그아웃됐습니다."}

    admin_url = f"{settings.supabase_url}/auth/v1/admin/users/{current_user.id}/logout"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(admin_url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Don't fail the logout if Supabase Admin API errors — the client has
            # already cleared its local session. Log server-side (status only,
            # never the service-role key) and return success to the caller.
            logger.error(
                "Supabase Admin logout returned %s for user %s",
                e.response.status_code,
                current_user.id,
            )
        except httpx.RequestError:
            logger.error(
                "Supabase Admin logout network error for user %s", current_user.id
            )

    return {"message": "로그아웃됐습니다."}
