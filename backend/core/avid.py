from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict

AVID_PREFIX = "AVID-"
_AVID_RE = re.compile(r"^AVID-[0-9a-f]{64}$")


def generate_avid(public_key: str, metadata: Dict[str, Any], *, constitution_hash: str, created_at: datetime) -> str:
    """Generate a deterministic ApexVeritas Identity (AVID).

    AVID binds:
    - agent public key (registration-time credential)
    - agent metadata (name/owner/capabilities, etc.)
    - constitution hash (governance binding)
    - registration timestamp

    The output is human-recognizable and cryptographically derived:
    `AVID-` + SHA256( canonical JSON payload ).
    """
    payload = {
        "public_key": public_key,
        "metadata": metadata,
        "constitution_hash": constitution_hash,
        "created_at": created_at.isoformat() + "Z",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return f"{AVID_PREFIX}{digest}"


def validate_avid_format(value: str) -> bool:
    """Return True if `value` matches the AVID format."""
    if not isinstance(value, str):
        return False
    return bool(_AVID_RE.match(value))

