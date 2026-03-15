"""add a2a sessions

Revision ID: 0009_add_a2a_sessions
Revises: 0008_add_audit_hash_chain
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_add_a2a_sessions"
down_revision = "0008_add_audit_hash_chain"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "a2a_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("initiator_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("responder_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("initiator_avid", sa.String(), nullable=False),
        sa.Column("responder_avid", sa.String(), nullable=False),
        sa.Column("initiator_nonce", sa.String(), nullable=False),
        sa.Column("responder_nonce", sa.String(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_a2a_sessions_session_id", "a2a_sessions", ["session_id"], unique=True)
    op.create_index("ix_a2a_sessions_initiator_agent_id", "a2a_sessions", ["initiator_agent_id"], unique=False)
    op.create_index("ix_a2a_sessions_responder_agent_id", "a2a_sessions", ["responder_agent_id"], unique=False)
    op.create_index("ix_a2a_sessions_initiator_avid", "a2a_sessions", ["initiator_avid"], unique=False)
    op.create_index("ix_a2a_sessions_responder_avid", "a2a_sessions", ["responder_avid"], unique=False)
    op.create_index("ix_a2a_sessions_created_at", "a2a_sessions", ["created_at"], unique=False)
    op.create_index("ix_a2a_sessions_expires_at", "a2a_sessions", ["expires_at"], unique=False)


def downgrade():
    op.drop_index("ix_a2a_sessions_expires_at", table_name="a2a_sessions")
    op.drop_index("ix_a2a_sessions_created_at", table_name="a2a_sessions")
    op.drop_index("ix_a2a_sessions_responder_avid", table_name="a2a_sessions")
    op.drop_index("ix_a2a_sessions_initiator_avid", table_name="a2a_sessions")
    op.drop_index("ix_a2a_sessions_responder_agent_id", table_name="a2a_sessions")
    op.drop_index("ix_a2a_sessions_initiator_agent_id", table_name="a2a_sessions")
    op.drop_index("ix_a2a_sessions_session_id", table_name="a2a_sessions")
    op.drop_table("a2a_sessions")

