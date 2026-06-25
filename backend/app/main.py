"""
NutriTrack FastAPI application entry point.

Startup responsibilities:
  - Mount CORS middleware using the allowlist from settings (never a wildcard in prod).
  - Register global exception handlers that return structured JSON errors and
    never expose stack traces, secret values, or internal service details.
  - Include all feature routers under /api/v1.
  - Expose a health check at /health for load-balancer / deployment readiness probes.

Security invariants:
  - debug=True is never set; Uvicorn's --reload flag is for local dev only.
  - Unhandled exceptions produce {"error": "Internal server error"} — not tracebacks.
  - HTTPExceptions pass through unchanged so route handlers retain full control
    over 4xx status codes and messages.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import auth as auth_router
from app.routers import meals as meals_router
from app.routers import analyze as analyze_router
from app.routers import nutrition as nutrition_router
from app.services.rate_limiter import RateLimitError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup validation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # SKIP_AUTH=true bypasses all authentication. It is never safe in production.
    # Refusing to start is the only reliable way to prevent accidental deployment.
    if settings.skip_auth and settings.environment != "development":
        raise RuntimeError(
            "SKIP_AUTH cannot be enabled outside of the development environment. "
            "Set ENVIRONMENT=development in your .env, or unset SKIP_AUTH."
        )
    if settings.skip_auth:
        logger.warning(
            "SKIP_AUTH is enabled — all requests are authenticated as the dev user. "
            "This must never reach production."
        )
    yield


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NutriTrack API",
    lifespan=lifespan,
    description=(
        "Backend API for NutriTrack — an AI-powered meal nutrition tracker. "
        "Provides food recognition via vision LLM, nutrition lookup, and meal history."
    ),
    version="0.1.0",
    # Docs UI is disabled in production to avoid leaking the full API surface.
    # Set ENVIRONMENT=development locally to enable /docs and /redoc.
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,  # never the raw comma-string
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Pass HTTPExceptions through with their original status code and detail.

    Route handlers raise HTTPException to communicate 4xx/5xx responses with
    specific messages; this handler serialises them into the project's standard
    {"error": "<message>"} envelope without swallowing or re-wrapping them.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    """
    Handle OpenRouter daily quota exhaustion.

    Returns a 429 with a user-friendly Korean message and a Retry-After header
    indicating the client should try again tomorrow (86400 seconds).
    The response body never contains internal details — only the pre-formatted
    Korean message and the remaining count (always 0 at this point).
    """
    return JSONResponse(
        status_code=429,
        content={"error": exc.message, "remaining": exc.remaining, "resets_at_utc": exc.resets_at_utc},
        headers={"Retry-After": "86400"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled exceptions.

    Logs the full exception server-side (with request path for traceability)
    and returns a generic client-safe message.  Stack traces, secret values,
    and internal service details are NEVER included in the response body.
    """
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(meals_router.router, prefix="/api/v1")
app.include_router(analyze_router.router, prefix="/api/v1")
app.include_router(nutrition_router.router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    tags=["ops"],
    summary="Health check",
    description="Returns 200 OK when the server is running. Used by load balancers and deployment readiness probes.",
    response_description='{"status": "ok"}',
)
async def health_check() -> dict[str, str]:
    """Liveness probe — no DB or external dependency check."""
    return {"status": "ok"}
