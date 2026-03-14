from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Dict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


def canonical_json_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sha256_digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def verify_hmac_sha256(secret: str, digest: bytes, signature: str) -> bool:
    mac = hmac.new(secret.encode("utf-8"), digest, hashlib.sha256).digest()
    sig = signature.strip()
    try:
        if all(c in "0123456789abcdefABCDEF" for c in sig) and len(sig) % 2 == 0:
            provided = bytes.fromhex(sig)
        else:
            provided = base64.b64decode(sig, validate=True)
    except Exception:
        return False
    return hmac.compare_digest(mac, provided)


def verify_ecdsa_p256_sha256(public_key_pem: str, digest: bytes, signature_b64: str) -> bool:
    try:
        pub = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(signature_b64, validate=True)
        assert isinstance(pub, ec.EllipticCurvePublicKey)
        pub.verify(signature, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        return True
    except (ValueError, InvalidSignature, AssertionError):
        return False

