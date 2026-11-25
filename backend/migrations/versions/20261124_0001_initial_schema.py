"""Initial CCI STEM Connect relational schema (all 30 tables).

Revision ID: 20261124_0001
Revises:
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

from app.database.base import Base
import app.models  # noqa: F401

revision: str = "20261124_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
