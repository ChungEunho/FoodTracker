"""
SQLAlchemy ORM models for NutriTrack (PostgreSQL / multi-user).

Design decisions:
- users.id is a UUID that mirrors the auth.users.id from Supabase Auth.
  Our public.users row is inserted on first login (by a Supabase DB trigger or
  a FastAPI dependency), giving the meals table a stable FK target in the public schema.
- meals.id is a BIGINT IDENTITY — monotonically increasing, cheap for internal joins.
  External APIs should expose meals.id as-is; no UUID indirection needed for meals.
- All timestamps use TIMESTAMPTZ (UTC-aware).  Never store naive datetimes.
- items_json / total_json are JSONB for efficient storage, indexing, and query support.

Query rules (enforced in all routers/services that touch meals):
1. Every SELECT/UPDATE/DELETE on meals MUST include WHERE user_id = <current_user_id>.
   There is NO legitimate cross-user query on this table.
2. Use SQLAlchemy ORM or text() with .bindparams() — never f-strings or % formatting.
   ORM style:  select(Meal).where(Meal.user_id == current_user.id)
   Raw style:  text("... WHERE user_id = :uid").bindparams(uid=user_id)
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """
    Mirrors auth.users from Supabase Auth in the public schema.

    id is the same UUID that Supabase assigns.  We do NOT generate it here;
    it is supplied by the caller (trigger or API layer) at insert time.
    """

    __tablename__ = "users"

    # Primary key: UUID supplied by Supabase Auth — same value as auth.users.id.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        # Default to gen_random_uuid() as a fallback; Supabase will always supply
        # the real value explicitly, so this default is a safety net only.
        server_default=func.gen_random_uuid(),
        comment="UUID from Supabase auth.users.id",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="User email, synced from Supabase Auth",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Row creation timestamp (UTC)",
    )

    # updated_at is not needed on users — we don't mutate this table after insert.
    # If profile data (display name, avatar) is added later, add updated_at at that point.

    # Relationship: one user → many meals.
    meals: Mapped[list["Meal"]] = relationship(
        "Meal",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,  # relies on DB-level ON DELETE CASCADE
    )


class Meal(Base):
    """
    One meal log entry, always scoped to a single user.

    IMPORTANT: every query on this table must filter by user_id.
    See module docstring for the mandatory query patterns.
    """

    __tablename__ = "meals"

    __table_args__ = (
        # PRIMARY access pattern: fetch all meals for a user on a given date.
        # Covers: WHERE user_id = ? AND date = ?
        # Also covers range queries: WHERE user_id = ? AND date BETWEEN ? AND ?
        Index("ix_meals_user_id_date", "user_id", "date"),
        # SECONDARY pattern: fetch all meals for a user (e.g., 기록 관리 tab).
        # Covers: WHERE user_id = ?  (without a date filter)
        Index("ix_meals_user_id", "user_id"),
        # Constraint: meal_type must be one of the four valid Korean meal names.
        CheckConstraint(
            "meal_type IN ('아침', '점심', '저녁', '간식')",
            name="ck_meals_meal_type",
        ),
    )

    # Internal auto-increment PK.  Not exposed as a UUID because this table is
    # append-only and internal sequential IDs are fine for client references.
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Internal sequential meal ID",
    )

    # FK to public.users.  ON DELETE CASCADE removes meals when a user account is deleted.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner user ID — MUST be filtered on every query",
    )

    # Date of the meal (not the log timestamp).  Stored as a native DATE column;
    # the original SQLite schema used TEXT which required application-level parsing.
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Calendar date of the meal (YYYY-MM-DD)",
    )

    meal_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Meal category: 아침 | 점심 | 저녁 | 간식",
    )

    # Originally a local filesystem path.  In the multi-user architecture this stores
    # a Supabase Storage object key or public URL, or NULL if the meal was entered
    # via text/manual input rather than an image upload.
    image_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Supabase Storage object key or URL (was local path in SQLite era)",
    )

    # Nutrition data as JSONB.  Shape:
    #   items_json — array of {name, weight_g, calories_kcal, carbs_g, protein_g, fat_g, ...}
    #   total_json — object {weight_g, calories_kcal, carbs_g, protein_g, fat_g, ...}
    # JSONB lets PostgreSQL index into these fields and supports containment queries
    # if we ever need them (e.g., find meals containing a specific item by name).
    items_json: Mapped[dict | list] = mapped_column(
        JSONB,
        nullable=False,
        comment="Array of recognized food items with per-item nutrition data",
    )

    total_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Aggregated nutrition totals for this meal entry",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Row creation timestamp (UTC)",
    )

    # HH:MM string representing the time the meal was eaten (user-supplied, optional).
    # Kept as VARCHAR(5) matching the original schema; could be migrated to TIME later.
    meal_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="Time the meal was eaten, HH:MM format (user-supplied, optional)",
    )

    # Relationship back to user.
    user: Mapped["User"] = relationship("User", back_populates="meals")
