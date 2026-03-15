from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Dict


def canonical_attestation_bytes(avid: str, issuer: str, claim_type: str, claim_value: Dict[str, Any]) -> bytes:
    payload = {
        "avid": avid,
        "issuer": issuer,
        "claim_type": claim_type,
        "claim_value": claim_value,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign_attestation_hmac(secret: str, avid: str, issuer: str, claim_type: str, claim_value: Dict[str, Any]) -> str:
    msg = canonical_attestation_bytes(avid, issuer, claim_type, claim_value)
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_attestation_hmac(secret: str, signature_b64: str, avid: str, issuer: str, claim_type: str, claim_value: Dict[str, Any]) -> bool:
    try:
        provided = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False
    msg = canonical_attestation_bytes(avid, issuer, claim_type, claim_value)
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return hmac.compare_digest(digest, provided)

