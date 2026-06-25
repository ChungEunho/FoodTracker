"""
In-memory async job registry for background analysis tasks.

Jobs are keyed by a UUID string and stored in a module-level dict.
Each job is scoped to the user who created it — callers MUST verify
job.user_id matches the requesting user before returning job data.

LIMITATIONS:
  - In-process only: jobs are lost on server restart.
  - No TTL / expiry: in a long-running deployment, stale jobs accumulate.
    A production implementation should use Redis with TTL (e.g. SETEX 3600)
    or a DB table with a periodic cleanup job.
  - Not safe for multi-process deployments: each worker has its own _store.
    Use Redis or a DB-backed store for multi-worker / multi-instance setups.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


@dataclass
class Job:
    """A single background analysis job."""

    id: str
    user_id: str                     # UUID as string — must match CurrentUser.id
    status: JobStatus
    result: dict | None = None       # populated when status == done
    error: str | None = None         # populated when status == failed (message only, no stack trace)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Module-level store ────────────────────────────────────────────────────────

_store: dict[str, Job] = {}
_lock: asyncio.Lock = asyncio.Lock()


# ── Public API ────────────────────────────────────────────────────────────────


async def create_job(user_id: str) -> Job:
    """
    Create a new job in the pending state.

    Args:
        user_id: UUID string of the requesting user.

    Returns:
        The newly created Job with a fresh UUID id.
    """
    job = Job(
        id=str(uuid.uuid4()),
        user_id=user_id,
        status=JobStatus.pending,
    )
    async with _lock:
        _store[job.id] = job
    return job


async def get_job(job_id: str) -> Job | None:
    """
    Retrieve a job by its id.

    Returns:
        The Job, or None if not found.
    """
    async with _lock:
        return _store.get(job_id)


async def update_job(job_id: str, **kwargs) -> None:
    """
    Update one or more fields of an existing job in place.

    Accepted kwargs: status, result, error.
    Silently does nothing if the job does not exist.

    Args:
        job_id: UUID string of the job to update.
        **kwargs: Field name → new value pairs.
    """
    async with _lock:
        job = _store.get(job_id)
        if job is None:
            return
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
