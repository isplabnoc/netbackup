"""production settings and job progress

Revision ID: 0002_production_settings_jobs
Revises: 0001_initial_schema
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_production_settings_jobs"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_app_settings_id", "app_settings", ["id"])
    op.create_index("ix_app_settings_key", "app_settings", ["key"], unique=True)
    op.add_column("backup_jobs", sa.Column("running", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("backup_jobs", sa.Column("error_message", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("backup_jobs", "error_message")
    op.drop_column("backup_jobs", "running")
    op.drop_table("app_settings")
