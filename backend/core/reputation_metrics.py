from __future__ import annotations

import math
from datetime import datetime
from typing import Optional


def effective_reputation(base_reputation: float, *, last_activity_at: Optional[datetime], half_life_days: float = 30.0) -> float:
    """Compute a simple time-decayed effective reputation.

    effective = base * exp(-days_since/half_life_days)
    """
    if base_reputation is None:
        base_reputation = 0.0
    if not last_activity_at:
        return float(base_reputation)
    days = max(0.0, (datetime.utcnow() - last_activity_at).total_seconds() / 86400.0)
    return float(base_reputation) * math.exp(-days / float(half_life_days))


def success_rate(tasks_success: int, tasks_failure: int) -> Optional[float]:
    denom = int(tasks_success or 0) + int(tasks_failure or 0)
    if denom <= 0:
        return None
    return float(tasks_success or 0) / float(denom)

