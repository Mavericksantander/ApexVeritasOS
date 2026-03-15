"""add peer attestations (agent vouches)

Revision ID: 0012_add_peer_attestations
Revises: 0011_add_trust_vector
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_add_peer_attestations"
down_revision = "0011_add_trust_vector"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_peer_attestations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("from_avid", sa.String(), nullable=False),
        sa.Column("target_avid", sa.String(), nullable=False),
        sa.Column("dimension", sa.String(), nullable=False),
        sa.Column("score_delta", sa.Float(), nullable=False),
        sa.Column("evidence_task_id", sa.Integer(), nullable=True),
        sa.Column("evidence_session_id", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_peer_attestations_from_agent_id", "agent_peer_attestations", ["from_agent_id"], unique=False)
    op.create_index("ix_agent_peer_attestations_from_avid", "agent_peer_attestations", ["from_avid"], unique=False)
    op.create_index("ix_agent_peer_attestations_target_avid", "agent_peer_attestations", ["target_avid"], unique=False)
    op.create_index("ix_agent_peer_attestations_dimension", "agent_peer_attestations", ["dimension"], unique=False)
    op.create_index("ix_agent_peer_attestations_evidence_task_id", "agent_peer_attestations", ["evidence_task_id"], unique=False)
    op.create_index("ix_agent_peer_attestations_evidence_session_id", "agent_peer_attestations", ["evidence_session_id"], unique=False)
    op.create_index("ix_agent_peer_attestations_created_at", "agent_peer_attestations", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_agent_peer_attestations_created_at", table_name="agent_peer_attestations")
    op.drop_index("ix_agent_peer_attestations_evidence_session_id", table_name="agent_peer_attestations")
    op.drop_index("ix_agent_peer_attestations_evidence_task_id", table_name="agent_peer_attestations")
    op.drop_index("ix_agent_peer_attestations_dimension", table_name="agent_peer_attestations")
    op.drop_index("ix_agent_peer_attestations_target_avid", table_name="agent_peer_attestations")
    op.drop_index("ix_agent_peer_attestations_from_avid", table_name="agent_peer_attestations")
    op.drop_index("ix_agent_peer_attestations_from_agent_id", table_name="agent_peer_attestations")
    op.drop_table("agent_peer_attestations")

