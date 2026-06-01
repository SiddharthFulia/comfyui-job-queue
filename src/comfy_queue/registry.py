from __future__ import annotations

from collections.abc import Callable
from typing import Any

from comfy_queue.job import Job


Handler = Callable[[Job, dict[str, Any]], dict[str, Any]]


registry: dict[str, Handler] = {}


class HandlerNotFound(KeyError):
    """Raised when a job arrives with a kind nobody registered for."""


def register(kind: str) -> Callable[[Handler], Handler]:
    """Decorator that adds ``fn`` to the registry under ``kind``."""

    def _wrap(fn: Handler) -> Handler:
        if kind in registry:
            raise ValueError(f"handler already registered for kind={kind!r}")
        registry[kind] = fn
        return fn

    return _wrap


def unregister(kind: str) -> None:
    registry.pop(kind, None)


def dispatch(job: Job, ctx: dict[str, Any]) -> dict[str, Any]:
    """Look up the handler for ``job.kind`` and call it."""
    fn = registry.get(job.kind)
    if fn is None:
        raise HandlerNotFound(job.kind)
    return fn(job, ctx)
