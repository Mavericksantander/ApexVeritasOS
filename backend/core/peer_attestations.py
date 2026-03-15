from __future__ import annotations

from datetime import datetime, timedelta
from math import exp
from typing import Dict

from sqlalchemy.orm import Session

from ..models import Agent, AgentPeerAttestation

_DIMENSIONS = {"competence", "safety", "availability", "transparency"}


def _weight_from_reputation(rep: float) -> float:
    # Smooth weight that approaches 1.0 as rep grows, stays near 0 for brand-new agents.
    rep = float(rep or 0.0)
    return float(1.0 - exp(-rep / 10.0))


def aggregate_peer_adjustments(
    db: Session,
    *,
    target_avid: str,
    window_days: int = 30,
    clamp: float = 0.15,
) -> Dict[str, float]:
    """Compute small peer adjustments per dimension (MVP).

    Weight each attestation by attester reputation to reduce fresh-sybil impact.
    Returns deltas clamped to +/- `clamp`.
    """
    if not target_avid:
        return {d: 0.0 for d in _DIMENSIONS}

    since = datetime.utcnow() - timedelta(days=int(window_days))
    rows = (
        db.query(AgentPeerAttestation, Agent.reputation_score)
        .join(Agent, Agent.agent_id == AgentPeerAttestation.from_agent_id)
        .filter(AgentPeerAttestation.target_avid == target_avid)
        .filter(AgentPeerAttestation.created_at >= since)
        .filter(AgentPeerAttestation.revoked == False)  # noqa: E712
        .order_by(AgentPeerAttestation.created_at.desc())
        .limit(200)
        .all()
    )
    sums: Dict[str, float] = {d: 0.0 for d in _DIMENSIONS}
    weights: Dict[str, float] = {d: 0.0 for d in _DIMENSIONS}
    for att, rep in rows:
        w = _weight_from_reputation(float(rep or 0.0))
        d = str(att.dimension)
        if d not in sums:
            continue
        sums[d] += float(att.score_delta) * w
        weights[d] += w
    out: Dict[str, float] = {}
    for d in _DIMENSIONS:
        if weights[d] <= 0:
            out[d] = 0.0
            continue
        avg = sums[d] / weights[d]
        if avg > clamp:
            avg = clamp
        if avg < -clamp:
            avg = -clamp
        out[d] = float(avg)
    return out

