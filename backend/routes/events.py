from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..core.events import broker, sse_stream
from ..core.rate_limiter import limiter, rate_limit_str

router = APIRouter()


@router.get("/events")
@limiter.limit(rate_limit_str)
def events(request: Request):
    q = broker.subscribe()
    return StreamingResponse(
        sse_stream(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

