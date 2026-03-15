from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

from .core import authorize_action
from .client import ApexRuntimeClient

T = TypeVar("T")


def _default_action_payload(args: tuple[Any, ...], kwargs: Dict[str, Any]) -> Any:
    # Heuristic: common tool patterns use a single string argument (cmd/path/url).
    if len(args) == 1 and isinstance(args[0], str) and not kwargs:
        return args[0]
    return {"args": list(args), "kwargs": dict(kwargs)}


def guard_tool(
    *,
    policy_file: str | Path = Path(__file__).with_name("policies.yaml"),
    audit_log_path: str | Path = "audit.log",
    agent_ctx: Optional[Dict[str, Any]] = None,
    action_type: Optional[str] = None,
    payload_builder: Optional[Callable[..., Any]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that gates a tool call behind `authorize_action`.

    Minimal usage:
      @guard_tool()
      def execute_shell(cmd: str): ...

    Recommended usage (explicit action mapping):
      @guard_tool(action_type="execute_shell", payload_builder=lambda cmd: {"command": cmd})
      def execute_shell(cmd: str): ...
    """

    def _decorator(fn: Callable[..., T]) -> Callable[..., T]:
        atype = action_type or fn.__name__

        @wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> T:
            ctx = agent_ctx or {}
            payload = payload_builder(*args, **kwargs) if payload_builder else _default_action_payload(args, kwargs)
            decision = authorize_action(
                ctx,
                atype,
                payload,
                policy_file=policy_file,
                audit_log_path=audit_log_path,
            )
            d = (decision.get("decision") or "").upper()
            if d == "DENY":
                raise PermissionError(decision.get("reason") or "Denied by policy")
            if d == "REQUIRE_APPROVAL":
                raise PermissionError(decision.get("reason") or "Requires approval")
            return fn(*args, **kwargs)

        return _wrapped

    return _decorator


def guard_tool_http(
    *,
    client: ApexRuntimeClient,
    agent_ctx: Dict[str, Any],
    action_type: str,
    payload_builder: Optional[Callable[..., Any]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that gates execution via the HTTP runtime gateway."""

    def _decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> T:
            payload = payload_builder(*args, **kwargs) if payload_builder else _default_action_payload(args, kwargs)
            decision = client.authorize_action(agent_ctx, action_type, payload)
            d = (decision.get("decision") or "").upper()
            if d == "DENY":
                raise PermissionError(decision.get("reason") or "Denied by policy")
            if d == "REQUIRE_APPROVAL":
                raise PermissionError(decision.get("reason") or "Requires approval")
            return fn(*args, **kwargs)

        return _wrapped

    return _decorator


# --- Optional integrations (dependency-free stubs) ---


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Dict[str, Any]


def guard_tool_call(
    *,
    agent_ctx: Dict[str, Any],
    tool_call: ToolCall,
    action_type: str,
    policy_file: str | Path = Path(__file__).with_name("policies.yaml"),
    audit_log_path: str | Path = "audit.log",
) -> Dict[str, Any]:
    """Universal wrapper: LLM/agent -> Apex -> tool.

    Use this from any framework adapter by mapping a tool invocation to:
      action_type + action_payload (tool_call.arguments).
    """
    return authorize_action(
        agent_ctx,
        action_type,
        tool_call.arguments,
        policy_file=policy_file,
        audit_log_path=audit_log_path,
    )


def make_langchain_callback_handler(
    *,
    agent_ctx: Dict[str, Any],
    policy_file: str | Path = Path(__file__).with_name("policies.yaml"),
    audit_log_path: str | Path = "audit.log",
    action_type_prefix: str = "langchain_tool",
):
    """Create a LangChain CallbackHandler that authorizes tool execution.

    This is optional: it only works if LangChain is installed.
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError("LangChain is not installed (langchain-core).") from e

    class ApexGuardCallbackHandler(BaseCallbackHandler):
        def on_tool_start(self, serialized: Any, input_str: str | Dict[str, Any], **kwargs: Any) -> None:
            name = ""
            if isinstance(serialized, dict):
                name = str(serialized.get("name") or serialized.get("id") or "")
            action_type = f"{action_type_prefix}:{name}" if name else action_type_prefix
            payload: Any = input_str
            decision = authorize_action(
                agent_ctx,
                action_type,
                payload,
                policy_file=policy_file,
                audit_log_path=audit_log_path,
            )
            d = (decision.get("decision") or "").upper()
            if d != "ALLOW":
                raise RuntimeError(f"Blocked by Apex policy: {decision.get('reason')}")

    return ApexGuardCallbackHandler()


def crewai_wrap_tool(
    *,
    agent_ctx: Dict[str, Any],
    fn: Callable[..., T],
    action_type: str,
    payload_builder: Optional[Callable[..., Any]] = None,
    policy_file: str | Path = Path(__file__).with_name("policies.yaml"),
    audit_log_path: str | Path = "audit.log",
) -> Callable[..., T]:
    """CrewAI-friendly wrapper around a tool/executor call (no CrewAI dependency)."""

    @wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any) -> T:
        payload = payload_builder(*args, **kwargs) if payload_builder else _default_action_payload(args, kwargs)
        decision = authorize_action(
            agent_ctx,
            action_type,
            payload,
            policy_file=policy_file,
            audit_log_path=audit_log_path,
        )
        d = (decision.get("decision") or "").upper()
        if d != "ALLOW":
            raise RuntimeError(f"Blocked by Apex policy: {decision.get('reason')}")
        return fn(*args, **kwargs)

    return _wrapped


def autogpt_wrap_tool(
    *,
    agent_ctx: Dict[str, Any],
    fn: Callable[..., T],
    action_type: str,
    payload_builder: Optional[Callable[..., Any]] = None,
    policy_file: str | Path = Path(__file__).with_name("policies.yaml"),
    audit_log_path: str | Path = "audit.log",
) -> Callable[..., T]:
    """AutoGPT/Agents-SDK-friendly wrapper around a tool call (no dependency)."""
    return crewai_wrap_tool(
        agent_ctx=agent_ctx,
        fn=fn,
        action_type=action_type,
        payload_builder=payload_builder,
        policy_file=policy_file,
        audit_log_path=audit_log_path,
    )
