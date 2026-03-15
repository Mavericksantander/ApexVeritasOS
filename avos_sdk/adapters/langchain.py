from __future__ import annotations

from typing import Any, Callable, Dict

from .core import governed_tool


def as_langchain_tool(
    *,
    agent,
    name: str,
    description: str,
    action_type: str,
    payload_builder: Callable[[str], Dict[str, Any]],
    fn: Callable[[str], Any],
):
    """Return a LangChain-compatible callable without hard depending on LangChain.

    If LangChain is installed, you can wrap this into `Tool`/`StructuredTool`.
    """

    def _run(input_text: str) -> Any:
        executed, result, _decision = governed_tool(
            agent=agent,
            task_description=f"langchain:{name}",
            action_type=action_type,
            action_payload=payload_builder(input_text),
            fn=lambda: fn(input_text),
        )
        if not executed:
            raise RuntimeError(f"Blocked by AVOS: {name}")
        return result

    _run.__name__ = name
    _run.__doc__ = description
    return _run

