"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("public_key", sa.String(), nullable=False, unique=True),
        sa.Column("reputation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_tasks_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("result_status", sa.String(), nullable=False),
        sa.Column("execution_time", sa.Float(), nullable=True),
        sa.Column("logged_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "agent_reputation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "authorization_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "agent_heartbeats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reported_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("agent_heartbeats")
    op.drop_table("authorization_logs")
    op.drop_table("agent_reputation")
    op.drop_table("agent_tasks")
    op.drop_table("agents")
