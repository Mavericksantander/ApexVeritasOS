from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional


def canonical_hash_payload(data: Dict[str, Any]) -> str:
    """Return sha256 hex digest for a canonical JSON payload."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compute_chain_hash(
    *,
    prev_hash: Optional[str],
    fields: Dict[str, Any],
    namespace: str,
) -> str:
    """Compute an append-only hash-chain entry.

    The hash commits to:
    - namespace (e.g., authorization_log, a2a_message)
    - previous hash (or empty)
    - the record fields (canonical JSON)
    """
    payload = {
        "ns": namespace,
        "prev": prev_hash or "",
        "fields": fields,
    }
    return canonical_hash_payload(payload)

