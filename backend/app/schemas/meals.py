"""
Pydantic v2 schemas for the meals API.

Separation of concerns:
  MealCreate  — what the client sends when logging a meal.
  MealOut     — what the API serialises back to the client.

Internal ORM models (app.db.models.Meal) are never returned directly from
routes; FastAPI serialises MealOut instances instead.  This ensures that any
future ORM model changes do not silently alter the public API contract.
"""

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MealCreate(BaseModel):
    """
    Request body for POST /meals/.

    All fields are validated before the route handler runs.  Malformed
    requests are rejected with HTTP 422 Unprocessable Entity.
    """

    date: date_type = Field(..., description="Calendar date of the meal (YYYY-MM-DD)")

    meal_type: Literal["아침", "점심", "저녁", "간식"] = Field(
        ...,
        description="Meal category: 아침 (breakfast), 점심 (lunch), 저녁 (dinner), 간식 (snack)",
    )

    meal_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
        description="Time the meal was eaten in HH:MM format (optional)",
        examples=["12:30", "19:00"],
    )

    image_path: str | None = Field(
        default=None,
        description="Supabase Storage object key or public URL for the meal image (optional)",
    )

    items_json: list[dict[str, Any]] = Field(
        ...,
        description="Array of recognised food items with per-item nutrition data",
        examples=[
            [
                {
                    "name": "김치찌개",
                    "weight_g": 350,
                    "calories_kcal": 180,
                    "carbs_g": 12,
                    "protein_g": 14,
                    "fat_g": 7,
                }
            ]
        ],
    )

    total_json: dict[str, Any] = Field(
        ...,
        description="Aggregated nutrition totals for this meal entry",
        examples=[
            {
                "weight_g": 350,
                "calories_kcal": 180,
                "carbs_g": 12,
                "protein_g": 14,
                "fat_g": 7,
            }
        ],
    )


class MealOut(BaseModel):
    """
    Response schema for meal endpoints.

    from_attributes=True enables construction from SQLAlchemy ORM instances
    via model_validate(orm_obj) without manual field mapping.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Internal sequential meal ID")
    user_id: uuid.UUID = Field(..., description="UUID of the owning user")
    date: date_type = Field(..., description="Calendar date of the meal (YYYY-MM-DD)")
    meal_type: Literal["아침", "점심", "저녁", "간식"] = Field(
        ..., description="Meal category"
    )
    meal_time: str | None = Field(
        default=None, description="Time the meal was eaten (HH:MM), if provided"
    )
    image_path: str | None = Field(
        default=None, description="Supabase Storage URL for the meal image, if any"
    )
    items_json: list[dict[str, Any]] = Field(
        ..., description="Per-item nutrition data"
    )
    total_json: dict[str, Any] = Field(..., description="Aggregated nutrition totals")
    created_at: datetime = Field(..., description="Row creation timestamp (UTC)")
