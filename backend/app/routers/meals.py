"""
Meals router — CRUD endpoints for meal log entries.

Security contract (enforced on every route):
  1. All routes require an authenticated user via Depends(get_current_user).
  2. Every DB query filters by user_id = current_user.id — cross-user data
     access is structurally impossible given these WHERE clauses.
  3. DELETE uses WHERE id = ? AND user_id = ? so an attacker cannot delete
     another user's meal even if they know its numeric ID.
  4. NOT FOUND and FORBIDDEN are both surfaced as 404 — this prevents IDOR
     information leakage about the existence of resources owned by other users.
  5. SQLAlchemy ORM is used exclusively — no f-strings or %-formatting in SQL.

IDOR audit (last reviewed 2026-06-25):
  | Endpoint                 | User-owned resource | Ownership check                         |
  |--------------------------|---------------------|-----------------------------------------|
  | POST   /meals/           | Meal (created)      | user_id=current_user.id at insert       |
  | GET    /meals/daily      | Meal (list)         | WHERE user_id = current_user.id         |
  | DELETE /meals/{meal_id}  | Meal (delete)       | WHERE id=? AND user_id=?, else 404      |
  No endpoint fetches a resource by id alone; the ownership guard is in the
  query (not a post-fetch check). DELETE returns 404 for "not mine" — no leak.
"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, get_current_user
from app.db.models import Meal
from app.db.session import get_db
from app.schemas.meals import MealCreate, MealOut

router = APIRouter(
    prefix="/meals",
    tags=["meals"],
)


@router.post(
    "/",
    response_model=MealOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new meal entry",
    description=(
        "Creates a new meal entry for the authenticated user. "
        "Accepts a structured list of food items and their aggregated nutrition totals. "
        "The entry is permanently scoped to the requesting user and cannot be read "
        "or modified by any other user."
    ),
    response_description="The created meal entry including server-assigned id and created_at.",
)
async def create_meal(
    body: MealCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MealOut:
    """Insert a new meal row scoped to the authenticated user."""
    meal = Meal(
        user_id=current_user.id,
        date=body.date,
        meal_type=body.meal_type,
        meal_time=body.meal_time,
        image_path=body.image_path,
        items_json=body.items_json,
        total_json=body.total_json,
    )
    db.add(meal)
    await db.commit()
    await db.refresh(meal)
    return MealOut.model_validate(meal)


@router.get(
    "/daily",
    response_model=list[MealOut],
    summary="List meals for a specific date",
    description=(
        "Returns all meal entries logged by the authenticated user on the given date. "
        "Results are ordered by meal_time (nulls last) then by creation time."
    ),
    response_description="Array of meal entries for the requested date (may be empty).",
)
async def list_daily_meals(
    date: date_type,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MealOut]:
    """Fetch all meals for current_user on the given date."""
    stmt = (
        select(Meal)
        .where(Meal.user_id == current_user.id)
        .where(Meal.date == date)
        .order_by(Meal.meal_time.nulls_last(), Meal.created_at)
    )
    result = await db.execute(stmt)
    meals = result.scalars().all()
    return [MealOut.model_validate(m) for m in meals]


@router.delete(
    "/{meal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a meal entry",
    description=(
        "Permanently deletes the specified meal entry. "
        "The meal must belong to the authenticated user. "
        "Returns 404 whether the meal does not exist OR belongs to another user — "
        "this prevents IDOR information leakage about other users' meal IDs."
    ),
    response_description="No content on success.",
)
async def delete_meal(
    meal_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Delete a meal row using a compound WHERE clause (id AND user_id).

    The AND user_id = ? guard ensures that even if an attacker supplies a
    valid meal_id belonging to another user, the row is not deleted and the
    attacker learns nothing beyond a 404 response.
    """
    stmt = (
        delete(Meal)
        .where(Meal.id == meal_id)
        .where(Meal.user_id == current_user.id)
        .returning(Meal.id)
    )
    result = await db.execute(stmt)
    deleted_id = result.scalar_one_or_none()

    if deleted_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
