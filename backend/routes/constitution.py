from __future__ import annotations

from fastapi import APIRouter

from ..core.constitution import as_public_document

router = APIRouter()


@router.get("/constitution")
def get_constitution():
    """Expose the active constitution summary + hash used by AVOS guardrails."""
    return as_public_document()

