from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    avid: str
    action_type: str
    decision: str
    reason: str
    prev_hash: str
    entry_hash: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "avid": self.avid,
            "action_type": self.action_type,
            "decision": self.decision,
            "reason": self.reason,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


class HashChainAuditLog:
    """Append-only JSONL audit log with a simple hash chain."""

    def __init__(self, path: str | Path = "audit.log"):
        self.path = Path(path)

    def _read_last_entry_hash(self) -> str:
        if not self.path.exists():
            return ""
        last_line = ""
        with self.path.open("rb") as f:
            for line in f:
                if line.strip():
                    last_line = line.decode("utf-8")
        if not last_line:
            return ""
        try:
            obj = json.loads(last_line)
            return str(obj.get("entry_hash", "") or "")
        except Exception:
            return ""

    def append(
        self,
        *,
        avid: str,
        action_type: str,
        decision: str,
        reason: str,
        timestamp: Optional[str] = None,
    ) -> AuditEntry:
        prev_hash = self._read_last_entry_hash()
        ts = timestamp or _now_iso()
        base = {
            "timestamp": ts,
            "avid": avid,
            "action_type": action_type,
            "decision": decision,
            "reason": reason,
            "prev_hash": prev_hash,
        }
        entry_hash = _sha256_hex(prev_hash.encode("utf-8") + _canonical_json(base))
        entry = AuditEntry(
            timestamp=ts,
            avid=avid,
            action_type=action_type,
            decision=decision,
            reason=reason,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")
        return entry

    def iter_entries(self) -> Iterable[Dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def verify_integrity(self) -> bool:
        prev_hash = ""
        for entry in self.iter_entries():
            base = {
                "timestamp": entry.get("timestamp"),
                "avid": entry.get("avid"),
                "action_type": entry.get("action_type"),
                "decision": entry.get("decision"),
                "reason": entry.get("reason"),
                "prev_hash": entry.get("prev_hash", ""),
            }
            if str(entry.get("prev_hash", "")) != prev_hash:
                return False
            expected = _sha256_hex(prev_hash.encode("utf-8") + _canonical_json(base))
            if str(entry.get("entry_hash", "")) != expected:
                return False
            prev_hash = expected
        return True
