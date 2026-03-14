"""add severity column

Revision ID: 0003_add_severity
Revises: 0001_initial
Create Date: 2026-03-13 00:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_severity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("authorization_logs", sa.Column("severity", sa.String(), nullable=False, server_default="low"))


def downgrade():
    op.drop_column("authorization_logs", "severity")
