"""device ssh port

Revision ID: 0003_device_ssh_port
Revises: 0002_production_settings_jobs
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_device_ssh_port"
down_revision: str | None = "0002_production_settings_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"))


def downgrade() -> None:
    op.drop_column("devices", "ssh_port")
