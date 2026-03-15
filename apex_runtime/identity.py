from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def generate_avid(agent_metadata: Dict[str, Any]) -> str:
    """Generate an AVID identifier for audit/internal usage.

    Notes:
    - This is intentionally "invisible": it should not be marketed as a user feature.
    - The input should include a stable timestamp (e.g., `created_at`) if you want a stable AVID.
      If missing, we fall back to "now", which makes the AVID unique but not stable across processes.
    """
    meta = dict(agent_metadata or {})
    public_key = str(meta.get("public_key", "") or "")

    created_at = meta.get("created_at")
    if not created_at:
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        meta["created_at"] = created_at

    payload = {
        "public_key": public_key,
        "metadata": {k: v for k, v in meta.items() if k != "public_key"},
        "created_at": created_at,
    }
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return f"AVID-{digest}"
