"""
Nutrition search router — brand/menu nutrition lookup.

Endpoint:
  POST /nutrition/search — search nutrition by brand + menu name

The search cascades through multiple tiers (MFDS DB → SerpAPI → CalorieNinjas
→ LLM direct estimate) as implemented in nutrition_search_service.py.

The endpoint is synchronous from the client's perspective (no background job),
but LLM calls within the service are async and run under the event loop.
Expected latency: < 5 seconds for DB hits, up to 15–20 seconds for LLM fallback.

IDOR audit (last reviewed 2026-06-25):
  | Endpoint               | User-owned resource | Ownership check                       |
  |------------------------|---------------------|---------------------------------------|
  | POST /nutrition/search | None (stateless)    | N/A — no resource id, no persistence  |
  Search is stateless: it takes no resource id, persists nothing user-scoped,
  and returns only public nutrition data. No IDOR surface. Still requires auth
  (Depends(get_current_user)) so the OpenRouter quota cannot be drained anon.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import CurrentUser, get_current_user
from app.schemas.analyze import NutritionSearchRequest, NutritionSearchResponse
from app.services import rate_limiter
from app.services.nutrition_search_service import search_nutrition

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/nutrition",
    tags=["nutrition"],
)


@router.post(
    "/search",
    response_model=NutritionSearchResponse,
    summary="Search nutrition by brand and menu name",
    description=(
        "Search for nutrition information for a brand/menu combination. "
        "At least one of `brand` or `menu` must be non-empty. "
        "Search falls through multiple tiers: "
        "Korean — MFDS DB → Google/SerpAPI → LLM estimate; "
        "English — MFDS DB → CalorieNinjas → Google/SerpAPI → LLM estimate. "
        "Returns 404 if no nutrition data could be found."
    ),
    response_description="Nutrition result with items, totals, and rate limit usage.",
)
async def search_nutrition_endpoint(
    body: NutritionSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> NutritionSearchResponse:
    """
    Look up nutrition information for a brand/menu combination.

    Pre-flight rate limit check — if remaining == 0, return 429 before
    dispatching any LLM calls.  (DB and CalorieNinja calls don't consume
    OpenRouter quota, so the check is conservative for those tiers.)
    """
    usage = await rate_limiter.get_usage()
    if usage["remaining"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "OpenRouter 일일 요청 한도(50회)를 초과했습니다. "
                "내일 UTC 자정에 초기화됩니다."
            ),
        )

    result, found_name, is_exact = await search_nutrition(
        brand=body.brand,
        menu=body.menu,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="영양정보를 찾을 수 없습니다.",
        )

    updated_usage = await rate_limiter.get_usage()

    logger.info(
        "Nutrition search completed: brand=%r menu=%r found_name=%r is_exact=%s user_id=%s",
        body.brand,
        body.menu,
        found_name,
        is_exact,
        str(current_user.id),
    )

    return NutritionSearchResponse(
        result=result,
        found_name=found_name,
        is_exact=is_exact,
        rate_limit=updated_usage,
    )
