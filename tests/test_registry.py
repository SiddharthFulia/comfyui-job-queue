from __future__ import annotations

import pytest

from comfy_queue.job import Job
from comfy_queue.registry import HandlerNotFound, dispatch, register, registry, unregister


def test_register_and_dispatch():
    @register("test-kind")
    def _handler(job, ctx):
        return {"ok": True, "id": job.id, "ctx": ctx.get("foo")}

    j = Job(id="job-1", kind="test-kind", lane="image")
    out = dispatch(j, {"foo": 42})
    assert out == {"ok": True, "id": "job-1", "ctx": 42}


def test_register_rejects_duplicate():
    @register("dup")
    def _a(job, ctx):
        return {}

    with pytest.raises(ValueError):
        @register("dup")
        def _b(job, ctx):
            return {}


def test_dispatch_missing_kind():
    j = Job(id="x", kind="does-not-exist", lane="image")
    with pytest.raises(HandlerNotFound):
        dispatch(j, {})


def test_unregister_removes_handler():
    @register("temp")
    def _h(job, ctx):
        return {}

    assert "temp" in registry
    unregister("temp")
    assert "temp" not in registry
