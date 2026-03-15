from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TrustVector:
    """Explainable, multi-dimensional trust signal for an agent.

    This is intentionally lightweight for MVP: it is derived from existing counters and timestamps,
    then persisted as a JSON blob on the Agent row for fast reads and easy observability.
    """

    competence: float
    safety: float
    availability: float
    transparency: float
    version: str = "1"
    updated_at: Optional[datetime] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": (self.updated_at or datetime.utcnow()).isoformat() + "Z",
            "competence": float(self.competence),
            "safety": float(self.safety),
            "availability": float(self.availability),
            "transparency": float(self.transparency),
        }


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


def compute_trust_vector(
    *,
    tasks_success: int,
    tasks_failure: int,
    blocked_action_count: int,
    invalid_signature_count: int,
    last_heartbeat_at: Optional[datetime],
    peer_adjustments: Optional[Dict[str, float]] = None,
    now: Optional[datetime] = None,
) -> TrustVector:
    """Compute a minimal trust vector from existing agent signals.

    Dimensions (MVP):
    - competence: success rate (0..1). Unknown => 0.0.
    - safety: penalizes blocked actions and invalid signatures (0..1).
    - availability: heartbeat recency (0..1).
    - transparency: penalizes invalid signatures; rewards consistent signing (0..1).

    Notes:
    - This is an MVP heuristic, not a "truth" score. It is designed to be stable and explainable.
    - Future versions can add predictability, peer attestations, and capability-scoped competence.
    """
    now = now or datetime.utcnow()
    s = int(tasks_success or 0)
    f = int(tasks_failure or 0)
    total = s + f

    # Competence: success rate, but conservative when there is no data.
    competence = (float(s) / float(total)) if total > 0 else 0.0

    # Safety: blocked actions per attempted outcomes + invalid signatures penalty.
    blocked = int(blocked_action_count or 0)
    invalid = int(invalid_signature_count or 0)
    # Normalize by activity; +1 to keep sane at low sample sizes.
    blocked_ratio = float(blocked) / float(total + 1)
    invalid_ratio = float(invalid) / float(total + 1)
    safety = 1.0 - (0.65 * blocked_ratio + 0.35 * invalid_ratio)
    safety = _clamp01(safety)

    # Availability: 1.0 if heartbeat < 5m, linearly decays to 0.0 by 30m, else 0.0.
    availability = 0.0
    if last_heartbeat_at:
        age = now - last_heartbeat_at
        if age <= timedelta(minutes=5):
            availability = 1.0
        elif age <= timedelta(minutes=30):
            # 5m -> 1.0, 30m -> 0.0
            availability = 1.0 - ((age - timedelta(minutes=5)).total_seconds() / (25 * 60))
        else:
            availability = 0.0
    availability = _clamp01(availability)

    # Transparency: start from competence baseline, apply strong penalty for signature failures.
    # If an agent accumulates invalid signatures, it is either misconfigured or malicious.
    transparency = competence
    if invalid > 0:
        transparency = transparency * (1.0 / (1.0 + float(invalid)))
    transparency = _clamp01(transparency)

    # Optional peer adjustments (vouches). Keep it small and clamp.
    if peer_adjustments:
        competence = _clamp01(competence + float(peer_adjustments.get("competence", 0.0) or 0.0))
        safety = _clamp01(safety + float(peer_adjustments.get("safety", 0.0) or 0.0))
        availability = _clamp01(availability + float(peer_adjustments.get("availability", 0.0) or 0.0))
        transparency = _clamp01(transparency + float(peer_adjustments.get("transparency", 0.0) or 0.0))

    return TrustVector(
        competence=competence,
        safety=safety,
        availability=availability,
        transparency=transparency,
        updated_at=now,
    )
