from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from .core import governed_tool

T = TypeVar("T")


def openclaw_governed_call(
    *,
    agent,
    tool_name: str,
    action_type: str,
    action_payload: Dict[str, Any],
    fn: Callable[[], T],
) -> Tuple[bool, Optional[T], Dict[str, Any]]:
    """OpenClaw-friendly wrapper.

    Use this when implementing an OpenClaw 'skill' or tool:
    - map the tool invocation into (action_type, action_payload)
    - execute only if AVOS allows
    """
    return governed_tool(
        agent=agent,
        task_description=f"openclaw:{tool_name}",
        action_type=action_type,
        action_payload=action_payload,
        fn=fn,
    )

