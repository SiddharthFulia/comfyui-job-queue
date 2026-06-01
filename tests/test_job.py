from __future__ import annotations

import pytest
from pydantic import ValidationError

from comfy_queue.job import Job, JobStatus


def test_job_minimal_fields():
    j = Job(id="abc", kind="image", lane="image")
    assert j.id == "abc"
    assert j.status is JobStatus.PENDING
    assert j.payload == {}
    assert j.attempts == 0


def test_job_with_status_returns_copy():
    j = Job(id="abc", kind="image", lane="image")
    running = j.with_status(JobStatus.RUNNING)
    assert running is not j
    assert running.status is JobStatus.RUNNING
    assert j.status is JobStatus.PENDING


def test_job_missing_required():
    with pytest.raises(ValidationError):
        Job(kind="image", lane="image")  # type: ignore[call-arg]


def test_job_allows_extra_keys():
    j = Job.model_validate(
        {"id": "x", "kind": "image", "lane": "image", "_internal": {"trace": "..."}}
    )
    assert getattr(j, "_internal", None) == {"trace": "..."}


def test_job_status_enum_serializes_to_string():
    j = Job(id="abc", kind="image", lane="image", status=JobStatus.RUNNING)
    dumped = j.model_dump()
    assert dumped["status"] == "running"
