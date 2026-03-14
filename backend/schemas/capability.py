from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class CapabilityItem(BaseModel):
    name: str
    version: str = "1.0"

    model_config = ConfigDict(extra="ignore")

    @field_validator("name", mode="before")
    @classmethod
    def _coerce_name(cls, value: Any) -> str:
        if isinstance(value, str):
            return value
        raise TypeError("CapabilityItem.name must be a string")


def normalize_capabilities(value: Any) -> list[dict[str, str]]:
    """Accept legacy list[str] or list[CapabilityItem|dict] and return JSON-friendly list[dict]."""
    if value is None:
        return []
    if isinstance(value, list):
        normalized: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"name": item, "version": "1.0"})
                continue
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                normalized.append({"name": name, "version": str(item.get("version") or "1.0")})
                continue
            if isinstance(item, CapabilityItem):
                normalized.append({"name": item.name, "version": item.version})
                continue
        return normalized
    return []


def capability_names(capabilities: Any) -> list[str]:
    """Return list of capability names from legacy or structured formats."""
    if not capabilities:
        return []
    if isinstance(capabilities, list):
        names: list[str] = []
        for item in capabilities:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return names
    return []

