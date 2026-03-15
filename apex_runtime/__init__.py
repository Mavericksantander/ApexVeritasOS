"""ApexVeritas minimal Agent Safety Runtime.

This package intentionally focuses on a single adoptable primitive:
`authorize_action` + minimal audit hash-chain + invisible AVID generation.
"""

from .core import Decision, authorize_action
from .client import ApexRuntimeClient
from .identity import generate_avid
from .middleware import guard_tool

__all__ = ["ApexRuntimeClient", "Decision", "authorize_action", "generate_avid", "guard_tool"]
