from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):  # noqa: UP042 - keep str+Enum mix for backwards-compat with consumers that compare to raw strings
    PENDING = "pending"
    PICKED = "picked"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    DEAD = "dead"


class Job(BaseModel):
    """A unit of work routed to a single lane."""

    model_config = {"extra": "allow"}

    id: str
    kind: str
    lane: str
    model: str | None = None
    prompt: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    callback_url: str | None = None

    def with_status(self, status: JobStatus) -> Job:
        """Return a copy of the job with a new status."""
        return self.model_copy(update={"status": status})
