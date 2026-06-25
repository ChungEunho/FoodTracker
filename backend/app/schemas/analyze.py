"""
Pydantic v2 schemas for the analyze and nutrition search endpoints.

JobStatusResponse — response for GET /analyze/jobs/{job_id}
NutritionSearchRequest — request body for POST /nutrition/search
NutritionSearchResponse — response for POST /nutrition/search
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class JobStatusResponse(BaseModel):
    """Response schema for job status polling."""

    job_id: str = Field(..., description="UUID of the background job")
    status: Literal["pending", "running", "done", "failed"] = Field(
        ..., description="Current job status"
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Populated when status='done'. Contains meal_id, items, total, image_url."
        ),
    )
    error: str | None = Field(
        default=None,
        description="User-facing error message when status='failed'.",
    )
    created_at: datetime = Field(
        ..., description="UTC timestamp when the job was created"
    )


class JobAcceptedResponse(BaseModel):
    """Immediate 202 response when a job is enqueued."""

    job_id: str = Field(..., description="UUID to poll via GET /analyze/jobs/{job_id}")
    status: Literal["pending"] = Field(default="pending")


class NutritionSearchRequest(BaseModel):
    """Request body for POST /nutrition/search."""

    brand: str = Field(
        default="",
        description="Brand name (e.g. 스타벅스). At least one of brand/menu must be non-empty.",
    )
    menu: str = Field(
        default="",
        description="Menu item name (e.g. 아이스 아메리카노 그란데). At least one of brand/menu must be non-empty.",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "NutritionSearchRequest":
        if not self.brand.strip() and not self.menu.strip():
            raise ValueError("brand 또는 menu 중 하나 이상은 반드시 입력해야 합니다.")
        return self


class NutritionSearchResponse(BaseModel):
    """Response schema for POST /nutrition/search."""

    result: dict[str, Any] = Field(
        ..., description="Nutrition result with items and total keys"
    )
    found_name: str | None = Field(
        default=None, description="Product name that was matched"
    )
    is_exact: bool = Field(
        ..., description="True if matched from a structured data source"
    )
    rate_limit: dict[str, Any] = Field(
        ..., description="Current OpenRouter daily usage stats"
    )
