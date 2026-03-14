import logging
import structlog

from structlog.contextvars import clear_contextvars, bind_contextvars


def configure_logging() -> structlog.BoundLogger:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    bind_contextvars(app="avos")
    return structlog.get_logger()


def reset_context() -> None:
    clear_contextvars()


def bind_request(request_id: str, agent_id: str | None = None, reputation_delta: float | None = None) -> None:
    context = {"request_id": request_id}
    if agent_id:
        context["agent_id"] = agent_id
    if reputation_delta is not None:
        context["reputation_delta"] = reputation_delta
    bind_contextvars(**context)
