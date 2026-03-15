"""add agent attestations (registry)

Revision ID: 0010_add_registry_attestations
Revises: 0009_add_a2a_sessions
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_add_registry_attestations"
down_revision = "0009_add_a2a_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_attestations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("avid", sa.String(), nullable=False),
        sa.Column("issuer", sa.String(), nullable=False),
        sa.Column("claim_type", sa.String(), nullable=False),
        sa.Column("claim_value", sa.JSON(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_attestations_agent_id", "agent_attestations", ["agent_id"], unique=False)
    op.create_index("ix_agent_attestations_avid", "agent_attestations", ["avid"], unique=False)
    op.create_index("ix_agent_attestations_issuer", "agent_attestations", ["issuer"], unique=False)
    op.create_index("ix_agent_attestations_claim_type", "agent_attestations", ["claim_type"], unique=False)
    op.create_index("ix_agent_attestations_created_at", "agent_attestations", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_agent_attestations_created_at", table_name="agent_attestations")
    op.drop_index("ix_agent_attestations_claim_type", table_name="agent_attestations")
    op.drop_index("ix_agent_attestations_issuer", table_name="agent_attestations")
    op.drop_index("ix_agent_attestations_avid", table_name="agent_attestations")
    op.drop_index("ix_agent_attestations_agent_id", table_name="agent_attestations")
    op.drop_table("agent_attestations")

