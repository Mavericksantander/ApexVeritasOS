"""add policies and agent_keys tables

Revision ID: 0004_add_policies_and_agent_keys
Revises: 0003_add_severity
Create Date: 2026-03-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_add_policies_and_agent_keys"
down_revision = "0003_add_severity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_keys",
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), primary_key=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policies_name", "policies", ["name"], unique=True)

    policies = sa.table(
        "policies",
        sa.column("name", sa.String()),
        sa.column("pattern", sa.Text()),
        sa.column("action", sa.String()),
        sa.column("severity", sa.Integer()),
    )
    op.bulk_insert(
        policies,
        [
            {"name": "deny_rm_rf", "pattern": "rm -rf", "action": "deny", "severity": 10},
            {"name": "deny_sudo", "pattern": "sudo", "action": "deny", "severity": 9},
            {"name": "deny_sensitive_paths", "pattern": "/etc", "action": "deny", "severity": 9},
            {"name": "deny_root_paths", "pattern": "/root", "action": "deny", "severity": 9},
            {"name": "approve_privileged_fs", "pattern": "chmod", "action": "require_approval", "severity": 7},
            {"name": "approve_privileged_owner", "pattern": "chown", "action": "require_approval", "severity": 7},
            {"name": "approve_disk_tools", "pattern": "mkfs", "action": "require_approval", "severity": 8},
            {"name": "approve_raw_copy", "pattern": "dd ", "action": "require_approval", "severity": 8},
        ],
    )


def downgrade():
    op.drop_index("ix_policies_name", table_name="policies")
    op.drop_table("policies")
    op.drop_table("agent_keys")

