"""add trust vector snapshot to agents

Revision ID: 0011_add_trust_vector
Revises: 0010_add_registry_attestations
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_add_trust_vector"
down_revision = "0010_add_registry_attestations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("trust_vector", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("trust_updated_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("agents", "trust_updated_at")
    op.drop_column("agents", "trust_vector")

