"""Framework adapters for AVOS governance.

These adapters are dependency-light. They provide patterns you can plug into
OpenClaw, LangChain, or CrewAI without forcing AVOS to depend on those frameworks.
"""

from .core import governed_tool

__all__ = ["governed_tool"]

