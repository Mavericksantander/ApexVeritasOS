from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

T = TypeVar("T")


def governed_tool(
    *,
    agent,
    task_description: str,
    action_type: str,
    action_payload: Dict[str, Any],
    fn: Callable[[], T],
    success_result_status: str = "success",
    failure_result_status: str = "failure",
) -> Tuple[bool, Optional[T], Dict[str, Any]]:
    """Run a function behind AVOS governance.

    1) Ask AVOS authorization for the action.
    2) If allowed, run the function.
    3) Log the task outcome to AVOS.

    Returns: (executed, result, decision_payload)
    """
    decision = agent.authorize_action(action_type, action_payload)
    decision_value = (decision.get("decision") or decision.get("status") or "").lower()
    if decision_value not in {"allow", "allowed", "ok"}:
        # Not executed; still log it as a failed/blocked task for traceability if desired.
        try:
            agent.log_task(f"{task_description} (blocked)", result_status=failure_result_status, execution_time=0.0)
        except Exception:
            pass
        return False, None, decision

    try:
        result = fn()
        agent.log_task(task_description, result_status=success_result_status, execution_time=0.0)
        return True, result, decision
    except Exception:
        try:
            agent.log_task(task_description, result_status=failure_result_status, execution_time=0.0)
        except Exception:
            pass
        raise

