"""
Supabase Storage upload service.

Uploads raw image bytes to a deterministic, user-scoped object path:
    users/{user_id}/{job_id}{ext}

SECURITY:
  - Uses settings.supabase_service_role_key — NEVER logged or returned to callers.
  - Object path is namespaced by user_id to prevent cross-user path collisions.
  - Gracefully degrades when Supabase is not configured (returns a placeholder
    path so local development works without a live Supabase project).
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BUCKET = "meal-images"


async def upload_image(
    user_id: str,
    job_id: str,
    data: bytes,
    content_type: str,
    ext: str,
) -> str:
    """
    Upload image bytes to Supabase Storage and return the public URL.

    The object is stored at: users/{user_id}/{job_id}{ext}
    Uses PUT (upsert semantics) — safe to retry if the job is restarted.

    Args:
        user_id:      UUID of the owning user (string form).
        job_id:       Unique job identifier used as the filename stem.
        data:         Raw image bytes.
        content_type: MIME type (e.g. "image/jpeg").
        ext:          File extension including dot (e.g. ".jpg").

    Returns:
        Public URL string for the uploaded object.

    Note:
        If supabase_url or supabase_service_role_key are not configured, logs a
        warning and returns a placeholder path so local dev can proceed without
        a live Supabase project.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning(
            "Supabase Storage not configured (missing supabase_url or supabase_service_role_key). "
            "Image will not be persisted; returning placeholder path."
        )
        return f"local://meal-images/users/{user_id}/{job_id}{ext}"

    object_path = f"users/{user_id}/{job_id}{ext}"
    upload_url = (
        f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{object_path}"
    )
    public_url = (
        f"{settings.supabase_url}/storage/v1/object/public/{BUCKET}/{object_path}"
    )

    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": content_type,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.put(upload_url, content=data, headers=headers)
        response.raise_for_status()

    logger.info("Image uploaded to Supabase Storage: %s", object_path)
    return public_url
