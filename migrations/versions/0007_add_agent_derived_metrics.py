"""add agent derived metrics

Revision ID: 0007_add_agent_derived_metrics
Revises: 0006_add_a2a_tables
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_add_agent_derived_metrics"
down_revision = "0006_add_a2a_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("tasks_success", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agents", sa.Column("tasks_failure", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agents", sa.Column("invalid_signature_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agents", sa.Column("blocked_action_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agents", sa.Column("last_task_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("agents", "last_task_at")
    op.drop_column("agents", "blocked_action_count")
    op.drop_column("agents", "invalid_signature_count")
    op.drop_column("agents", "tasks_failure")
    op.drop_column("agents", "tasks_success")

