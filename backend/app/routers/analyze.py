"""
Analyze router — food image recognition via async background job pattern.

Endpoints:
  POST /analyze/image   — upload image, enqueue recognition job, return 202 + job_id
  GET  /analyze/jobs/{job_id} — poll job status and retrieve result

The vision pipeline (recognize + nutrition_analyze) can take 10–60 seconds.
HTTP requests NEVER block for that duration.  The POST returns immediately with
a job_id; the client polls the GET endpoint until status is 'done' or 'failed'.

Security:
  - Both endpoints require an authenticated user.
  - Jobs are scoped by user_id: a user cannot poll another user's job by id.
    A job that exists but belongs to another user returns 404 (NOT 403) — the
    same response as a non-existent job — so an attacker cannot distinguish
    "exists but not yours" from "does not exist" and enumerate valid job ids.
  - Image bytes are size-checked (10MB) before any processing.
  - RateLimitError is caught in the background task and surfaced as job.error.

IDOR audit (last reviewed 2026-06-25):
  | Endpoint                    | User-owned resource | Ownership check                          |
  |-----------------------------|---------------------|------------------------------------------|
  | POST /analyze/image         | Job (created)       | job.user_id = current_user.id at create  |
  | GET  /analyze/jobs/{job_id} | Job (read)          | job.user_id == current_user.id, else 404 |
  Background DB writes (Meal) set user_id=current_user.id and run in a fresh
  AsyncSessionLocal() session owned by the task — never the request-scoped one.
"""

import asyncio
import logging
import os
from datetime import date as date_type

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.auth.deps import CurrentUser, get_current_user
from app.db.models import Meal
from app.db.session import AsyncSessionLocal
from app.schemas.analyze import JobAcceptedResponse, JobStatusResponse
from app.services import jobs as job_store
from app.services import nutrition_analyze, rate_limiter, recognize, storage
from app.services.jobs import JobStatus
from app.services.rate_limiter import RateLimitError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
)

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_MEAL_TYPES = {"아침", "점심", "저녁", "간식"}


# ── Background task ───────────────────────────────────────────────────────────


async def _run_analysis(
    job_id: str,
    image_bytes: bytes,
    ext: str,
    meal_type: str,
    meal_date: date_type,
    meal_time: str | None,
    current_user: CurrentUser,
) -> None:
    """
    Background task: run the full image → recognition → nutrition → DB save pipeline.

    This task MUST catch all exceptions and mark the job as failed — never let an
    exception propagate to the event loop (which would silently swallow it).

    DB writes use a fresh AsyncSessionLocal() session owned by THIS task, not the
    request-scoped session from Depends(get_db). The request handler returns (and
    its session is closed) before this task commits, so reusing that session would
    raise InvalidRequestError. The Meal row is scoped with user_id=current_user.id.
    """
    user_id = str(current_user.id)

    try:
        await job_store.update_job(job_id, status=JobStatus.running)

        # 1. Upload image to Supabase Storage
        content_type = f"image/{ext.lstrip('.') or 'jpeg'}"
        image_url = await storage.upload_image(
            user_id=user_id,
            job_id=job_id,
            data=image_bytes,
            content_type=content_type,
            ext=ext,
        )

        # 2. Step 1 — vision recognition
        step1_result = await recognize.recognize(image_bytes)

        # 3. Step 2 — nutrition estimation
        step2_result = await nutrition_analyze.analyze(step1_result)

        # 4. Persist to DB (user-scoped) — own session, own lifetime.
        async with AsyncSessionLocal() as db:
            # Ensure the user row exists before inserting the meal (FK guard).
            # Supabase Auth manages the canonical user store; our local users
            # table is a shadow that we populate on first interaction.
            from sqlalchemy import text
            await db.execute(
                text(
                    "INSERT INTO users (id, email, created_at) "
                    "VALUES (:id, :email, now()) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": current_user.id, "email": current_user.email},
            )

            meal = Meal(
                user_id=current_user.id,
                date=meal_date,
                meal_type=meal_type,
                meal_time=meal_time,
                image_path=image_url,
                items_json=step2_result.get("items", []),
                total_json=step2_result.get("total", {}),
            )
            db.add(meal)
            await db.commit()
            await db.refresh(meal)
            meal_id = meal.id
        # session is closed here, before the job is marked done

        # 5. Mark job done
        await job_store.update_job(
            job_id,
            status=JobStatus.done,
            result={
                "meal_id": meal_id,
                "items": step2_result.get("items", []),
                "total": step2_result.get("total", {}),
                "image_url": image_url,
            },
        )
        logger.info(
            "Job %s completed: meal_id=%s user_id=%s", job_id, meal_id, user_id
        )

    except RateLimitError:
        await job_store.update_job(
            job_id,
            status=JobStatus.failed,
            error=(
                "OpenRouter 일일 요청 한도(50회)를 초과했습니다. "
                "내일 UTC 자정에 초기화됩니다."
            ),
        )
        logger.warning("Job %s failed: rate limit exceeded (user_id=%s)", job_id, user_id)

    except Exception as exc:  # noqa: BLE001
        # Log full details server-side; surface only the message to the client.
        logger.exception(
            "Job %s failed with unhandled exception (user_id=%s)", job_id, user_id
        )
        await job_store.update_job(
            job_id,
            status=JobStatus.failed,
            error="분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/image",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a meal image for analysis",
    description=(
        "Accepts a meal image and enqueues a background recognition + nutrition job. "
        "Returns a job_id immediately (202 Accepted). "
        "Poll GET /analyze/jobs/{job_id} to retrieve the result when ready. "
        "The full pipeline can take 10–60 seconds."
    ),
    response_description="Job id and initial pending status.",
)
async def upload_image_for_analysis(
    file: UploadFile,
    meal_type: str = Form(...),
    date: date_type = Form(...),
    meal_time: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> JobAcceptedResponse:
    """
    Enqueue an image analysis job.

    Validates inputs, checks rate limit, reads the file, creates a job, and
    launches the background task.  Returns 202 immediately.
    """
    # Validate meal_type
    if meal_type not in _ALLOWED_MEAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"meal_type은 {sorted(_ALLOWED_MEAL_TYPES)} 중 하나여야 합니다.",
        )

    # Validate file content-type
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="이미지 파일(JPEG, PNG, WebP, HEIC)만 업로드할 수 있습니다.",
        )

    # Pre-flight rate limit check (avoid creating a job that will immediately fail)
    usage = await rate_limiter.get_usage()
    if usage["remaining"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "OpenRouter 일일 요청 한도(50회)를 초과했습니다. "
                "내일 UTC 자정에 초기화됩니다."
            ),
        )

    # Read file bytes — enforce 10 MB limit
    image_bytes = await file.read()
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="이미지 파일 크기는 10MB를 초과할 수 없습니다.",
        )

    # Derive file extension from content-type or original filename
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower() if filename else ""
    if not ext:
        ct_to_ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/heic": ".heic",
        }
        ext = ct_to_ext.get(content_type, ".jpg")

    # Create job and launch background task
    job = await job_store.create_job(user_id=str(current_user.id))

    asyncio.create_task(
        _run_analysis(
            job_id=job.id,
            image_bytes=image_bytes,
            ext=ext,
            meal_type=meal_type,
            meal_date=date,
            meal_time=meal_time,
            current_user=current_user,
        )
    )

    return JobAcceptedResponse(job_id=job.id, status="pending")


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll analysis job status",
    description=(
        "Returns the current status of a background analysis job. "
        "Status progresses: pending → running → done | failed. "
        "When done, the result field contains meal_id, items, total, and image_url."
    ),
    response_description="Current job status and result (when complete).",
)
async def get_job_status(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> JobStatusResponse:
    """
    Return the status and result of a background job.

    Returns 404 if the job does not exist OR belongs to another user. Using the
    same 404 for both cases prevents IDOR enumeration: an attacker cannot
    distinguish "exists but not yours" (which a 403 would reveal) from
    "does not exist" and so cannot probe for valid job ids.
    """
    job = await job_store.get_job(job_id)

    if job is None or job.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="분석 작업을 찾을 수 없습니다.",
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
    )
