"""add avid to agents

Revision ID: 0005_add_avid_to_agents
Revises: 0004_add_policies_and_agent_keys
Create Date: 2026-03-15 00:00:00.000000
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0005_add_avid_to_agents"
down_revision = "0004_add_policies_and_agent_keys"
branch_labels = None
depends_on = None


def _constitution_hash() -> str:
    try:
        from backend.core.constitution import constitution_hash as ch  # type: ignore

        return ch()
    except Exception:
        return "unknown"


def _generate_avid(public_key: str, metadata: dict, constitution_hash: str, created_at: datetime) -> str:
    payload = {
        "public_key": public_key,
        "metadata": metadata,
        "constitution_hash": constitution_hash,
        "created_at": created_at.isoformat() + "Z",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "AVID-" + hashlib.sha256(canonical).hexdigest()


def upgrade():
    op.add_column("agents", sa.Column("avid", sa.String(), nullable=True))
    op.create_index("ix_agents_avid", "agents", ["avid"], unique=True)

    bind = op.get_bind()
    ch = _constitution_hash()

    rows = bind.execute(
        sa.text(
            """
            SELECT
              a.agent_id AS agent_id,
              a.name AS name,
              a.owner_id AS owner_id,
              a.capabilities AS capabilities,
              a.public_key AS public_key_hashed,
              a.registered_at AS registered_at,
              k.public_key AS public_key_plain
            FROM agents a
            LEFT JOIN agent_keys k ON k.agent_id = a.agent_id
            """
        )
    ).mappings()

    for row in rows:
        created_at = row["registered_at"] or datetime.utcnow()
        public_key = row["public_key_plain"] or row["public_key_hashed"] or ""
        metadata = {
            "agent_name": row["name"],
            "owner_id": row["owner_id"],
            "capabilities": row["capabilities"] or [],
        }
        avid = _generate_avid(public_key, metadata, ch, created_at)
        bind.execute(
            sa.text("UPDATE agents SET avid = :avid WHERE agent_id = :agent_id"),
            {"avid": avid, "agent_id": row["agent_id"]},
        )


def downgrade():
    op.drop_index("ix_agents_avid", table_name="agents")
    op.drop_column("agents", "avid")

