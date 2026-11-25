"""Add event objectives, event pillars, question categories, and default event config columns.

Revision ID: 20261125_0002
Revises: 20261124_0001
Create Date: 2026-11-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.database.base import Base
import app.models  # noqa: F401

revision: str = "20261125_0002"
down_revision: str | None = "20261124_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    # 1. Create any brand-new tables (event_objectives, event_pillars, question_categories)
    Base.metadata.create_all(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    # 2. Add new columns to `events` if upgrading an existing database
    event_columns: list[sa.Column] = [
        sa.Column("headline", sa.String(240), nullable=True),
        sa.Column("introduction", sa.Text(), nullable=True),
        sa.Column("event_category", sa.String(160), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assessment_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("follow_up_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("public_visibility", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "reflection_cards_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "immediate_assessment_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "follow_up_30d_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "follow_up_60d_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "follow_up_90d_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("default_questionnaire_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("active_framework_id", sa.Uuid(as_uuid=True), nullable=True),
    ]
    for col in event_columns:
        if not _has_column(inspector, "events", col.name):
            op.add_column("events", col)

    # Make events.event_date nullable so confirmed dates are never fabricated
    if dialect != "sqlite":
        op.alter_column("events", "event_date", existing_type=sa.Date(), nullable=True)

    # 3. Add category_id to `questions`
    if not _has_column(inspector, "questions", "category_id"):
        op.add_column(
            "questions",
            sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=True),
        )

    # 4. Add assessment_stage to `questionnaires`
    if not _has_column(inspector, "questionnaires", "assessment_stage"):
        op.add_column(
            "questionnaires",
            sa.Column("assessment_stage", sa.String(40), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for tbl in ("event_objectives", "event_pillars", "question_categories"):
        if tbl in existing_tables:
            op.drop_table(tbl)
