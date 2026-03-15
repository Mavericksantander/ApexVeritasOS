"""add a2a tables

Revision ID: 0006_add_a2a_tables
Revises: 0005_add_avid_to_agents
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_add_a2a_tables"
down_revision = "0005_add_avid_to_agents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_signing_keys",
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), primary_key=True),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "a2a_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("to_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("from_avid", sa.String(), nullable=False),
        sa.Column("to_avid", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_a2a_messages_from_agent_id", "a2a_messages", ["from_agent_id"], unique=False)
    op.create_index("ix_a2a_messages_to_agent_id", "a2a_messages", ["to_agent_id"], unique=False)
    op.create_index("ix_a2a_messages_from_avid", "a2a_messages", ["from_avid"], unique=False)
    op.create_index("ix_a2a_messages_to_avid", "a2a_messages", ["to_avid"], unique=False)
    op.create_index("ix_a2a_messages_message_id", "a2a_messages", ["message_id"], unique=False)
    op.create_index("ix_a2a_messages_payload_sha256", "a2a_messages", ["payload_sha256"], unique=False)
    op.create_index("ix_a2a_messages_created_at", "a2a_messages", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_a2a_messages_created_at", table_name="a2a_messages")
    op.drop_index("ix_a2a_messages_payload_sha256", table_name="a2a_messages")
    op.drop_index("ix_a2a_messages_message_id", table_name="a2a_messages")
    op.drop_index("ix_a2a_messages_to_avid", table_name="a2a_messages")
    op.drop_index("ix_a2a_messages_from_avid", table_name="a2a_messages")
    op.drop_index("ix_a2a_messages_to_agent_id", table_name="a2a_messages")
    op.drop_index("ix_a2a_messages_from_agent_id", table_name="a2a_messages")
    op.drop_table("a2a_messages")
    op.drop_table("agent_signing_keys")

