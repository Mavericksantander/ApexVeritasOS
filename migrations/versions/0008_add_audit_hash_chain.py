"""add audit hash chain columns

Revision ID: 0008_add_audit_hash_chain
Revises: 0007_add_agent_derived_metrics
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_add_audit_hash_chain"
down_revision = "0007_add_agent_derived_metrics"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("authorization_logs", sa.Column("prev_hash", sa.String(), nullable=True))
    op.add_column("authorization_logs", sa.Column("entry_hash", sa.String(), nullable=True))
    op.create_index("ix_authorization_logs_entry_hash", "authorization_logs", ["entry_hash"], unique=False)

    op.add_column("a2a_messages", sa.Column("prev_hash", sa.String(), nullable=True))
    op.add_column("a2a_messages", sa.Column("entry_hash", sa.String(), nullable=True))
    op.create_index("ix_a2a_messages_entry_hash", "a2a_messages", ["entry_hash"], unique=False)


def downgrade():
    op.drop_index("ix_a2a_messages_entry_hash", table_name="a2a_messages")
    op.drop_column("a2a_messages", "entry_hash")
    op.drop_column("a2a_messages", "prev_hash")

    op.drop_index("ix_authorization_logs_entry_hash", table_name="authorization_logs")
    op.drop_column("authorization_logs", "entry_hash")
    op.drop_column("authorization_logs", "prev_hash")

