"""
0001 — Initial schema: users and meals tables.

Creates the full multi-user schema from scratch.

This migration establishes the PostgreSQL equivalent of the original SQLite
single-user schema, extended with:
  - A users table (mirrors Supabase auth.users.id)
  - user_id FK on meals for data isolation
  - JSONB columns replacing TEXT JSON storage
  - DATE column replacing TEXT date storage
  - TIMESTAMPTZ columns replacing TEXT timestamps
  - Composite index (user_id, date) for the primary access pattern
  - Single-column index (user_id) for user-scoped list queries

Revision ID: 0001
Revises: (none — this is the first migration)
Create Date: 2026-06-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic revision identifiers.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── Extension ────────────────────────────────────────────────────────────
    # pgcrypto provides gen_random_uuid() used as the server-side default for
    # users.id.  Safe to run even if the extension already exists.
    # Note: uuid-ossp provides uuid_generate_v4(), not gen_random_uuid(); pgcrypto
    # (or PostgreSQL 13+ core) is the correct provider for gen_random_uuid().
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── users ─────────────────────────────────────────────────────────────────
    # Stores the subset of Supabase Auth user attributes we need for FK references
    # and basic profile display.  The authoritative auth record lives in Supabase's
    # auth schema; this table is a projection into public for FK purposes.
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="UUID from Supabase auth.users.id",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            comment="User email, synced from Supabase Auth",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Row creation timestamp (UTC)",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ── meals ─────────────────────────────────────────────────────────────────
    op.create_table(
        "meals",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            comment="Internal sequential meal ID",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Owner user ID — MUST be filtered on every query",
        ),
        sa.Column(
            "date",
            sa.Date(),
            nullable=False,
            comment="Calendar date of the meal (YYYY-MM-DD)",
        ),
        sa.Column(
            "meal_type",
            sa.String(10),
            nullable=False,
            comment="Meal category: 아침 | 점심 | 저녁 | 간식",
        ),
        sa.Column(
            "image_path",
            sa.Text(),
            nullable=True,
            comment="Supabase Storage object key or URL (was local path in SQLite era)",
        ),
        sa.Column(
            "items_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Array of recognized food items with per-item nutrition data",
        ),
        sa.Column(
            "total_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Aggregated nutrition totals for this meal entry",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Row creation timestamp (UTC)",
        ),
        sa.Column(
            "meal_time",
            sa.String(5),
            nullable=True,
            comment="Time the meal was eaten, HH:MM format (user-supplied, optional)",
        ),
        # meal_type must be one of the four valid Korean meal names.
        sa.CheckConstraint(
            "meal_type IN ('아침', '점심', '저녁', '간식')",
            name="ck_meals_meal_type",
        ),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    # PRIMARY access pattern: daily view tab — fetch all meals for a user on a date.
    # Also covers date-range queries for the summary tab (user_id prefix is satisfied).
    op.create_index(
        "ix_meals_user_id_date",
        "meals",
        ["user_id", "date"],
    )

    # SECONDARY access pattern: record management tab — list all meals for a user.
    # The composite index above does NOT efficiently cover queries without a date
    # filter because the leading column is user_id but the optimizer may still
    # choose a sequential scan if selectivity is low; an explicit single-column
    # index makes the intent clear and can be used independently.
    op.create_index(
        "ix_meals_user_id",
        "meals",
        ["user_id"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_meals_user_id", table_name="meals")
    op.drop_index("ix_meals_user_id_date", table_name="meals")
    op.drop_table("meals")
    op.drop_table("users")
    # Leave uuid-ossp extension in place — it may be used by other schemas/tables
    # in a shared Supabase project.  Removing it could break unrelated objects.
