from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict

from .signatures import canonical_json_bytes, sha256_digest, verify_ecdsa_p256_sha256


def canonical_a2a_message_bytes(
    *,
    from_avid: str,
    to_avid: str,
    message_id: str,
    sent_at: datetime,
    message_type: str,
    payload: Dict[str, Any],
) -> bytes:
    """Build canonical bytes for A2A signature verification."""
    data = {
        "from_avid": from_avid,
        "to_avid": to_avid,
        "message_id": message_id,
        "sent_at": sent_at.isoformat() + "Z",
        "message_type": message_type,
        "payload": payload,
    }
    return canonical_json_bytes(data)


def payload_sha256_hex(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_a2a_signature(
    public_key_pem: str,
    *,
    from_avid: str,
    to_avid: str,
    message_id: str,
    sent_at: datetime,
    message_type: str,
    payload: Dict[str, Any],
    signature: str,
) -> bool:
    """Verify a signed A2A message using the registered ECDSA public key."""
    msg = canonical_a2a_message_bytes(
        from_avid=from_avid,
        to_avid=to_avid,
        message_id=message_id,
        sent_at=sent_at,
        message_type=message_type,
        payload=payload,
    )
    digest = sha256_digest(msg)
    return verify_ecdsa_p256_sha256(public_key_pem, digest, signature)

