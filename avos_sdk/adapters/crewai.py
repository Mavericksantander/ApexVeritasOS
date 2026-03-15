from __future__ import annotations

from typing import Any, Callable, Dict

from .core import governed_tool


def crewai_task_wrapper(
    *,
    agent,
    task_name: str,
    action_type: str,
    action_payload: Dict[str, Any],
    fn: Callable[[], Any],
):
    """CrewAI-friendly wrapper for governed task execution."""
    executed, result, decision = governed_tool(
        agent=agent,
        task_description=f"crewai:{task_name}",
        action_type=action_type,
        action_payload=action_payload,
        fn=fn,
    )
    return {"executed": executed, "result": result, "decision": decision}

