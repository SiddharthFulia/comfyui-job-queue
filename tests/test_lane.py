from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from comfy_queue.broker import BrokerHandle
from comfy_queue.job import Job
from comfy_queue.lane import LaneContext, _lane_loop, _process_job
from comfy_queue.registry import register


BACKEND = "http://localhost:4001/api"
CB_URL = "http://localhost:4001/api/jobs/callback"


@pytest.fixture
def ctx():
    return LaneContext(
        backend_url=BACKEND,
        callback_url=CB_URL,
        poll_interval_seconds=0.05,
    )


@respx.mock
def test_process_job_calls_handler_and_complete_callback(ctx):
    captured = {}

    @register("unit-test-kind")
    def _h(job, hctx):
        captured["job_id"] = job.id
        hctx["on_progress"](0.5, "halfway")
        return {"files": ["a.png"]}

    cb_route = respx.post(CB_URL).mock(return_value=httpx.Response(200))

    j = Job(id="lane-1", kind="unit-test-kind", lane="image")
    out = _process_job(j, ctx, {"image": "idle"})

    assert captured["job_id"] == "lane-1"
    assert out == {"files": ["a.png"]}
    bodies = [c.request.content for c in cb_route.calls]
    assert any(b'"event":"progress"' in b for b in bodies)
    assert any(b'"event":"complete"' in b for b in bodies)


@respx.mock
def test_process_job_sends_failed_on_handler_exception(ctx):
    @register("kaboom")
    def _h(job, hctx):
        raise RuntimeError("boom")

    cb_route = respx.post(CB_URL).mock(return_value=httpx.Response(200))

    j = Job(id="lane-2", kind="kaboom", lane="image")
    with pytest.raises(RuntimeError):
        _process_job(j, ctx, {"image": "idle"})

    bodies = [c.request.content for c in cb_route.calls]
    assert any(b'"event":"failed"' in b and b"RuntimeError" in b for b in bodies)


def test_lane_loop_pulls_from_broker_and_acks(ctx, fake_connection, fake_channel):
    @register("unit-broker")
    def _h(job, hctx):
        return {"ok": True}

    handle = BrokerHandle("amqp://x", lanes=("image",))
    with patch("comfy_queue.broker.pika.BlockingConnection", return_value=fake_connection):
        handle.open()

    fake_channel.push(
        "comfy.image",
        {"id": "broker-job-1", "kind": "unit-broker", "lane": "image"},
    )

    stop = threading.Event()
    lane_state: dict[str, str] = {}

    with patch("comfy_queue.lane.send_progress", return_value=True), \
         patch("comfy_queue.lane.send_complete", return_value=True), \
         patch("comfy_queue.lane.send_failed", return_value=True):
        t = threading.Thread(
            target=_lane_loop,
            args=("image", handle, ctx, lane_state, stop),
            daemon=True,
        )
        t.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not fake_channel.acked:
            time.sleep(0.05)
        stop.set()
        t.join(timeout=2.0)

    assert fake_channel.acked, "lane loop should have acked the job"


def test_lane_loop_falls_back_to_http_when_no_broker(ctx):
    poll_calls: list[str] = []

    @register("http-fallback")
    def _h(job, hctx):
        return {"ok": True}

    with respx.mock(assert_all_called=False) as router:
        def next_handler(request):
            poll_calls.append(str(request.url))
            if len(poll_calls) == 1:
                return httpx.Response(
                    200,
                    json={"id": "http-1", "kind": "http-fallback", "lane": "image"},
                )
            return httpx.Response(204)

        router.get(f"{BACKEND}/jobs/next").mock(side_effect=next_handler)
        router.post(f"{BACKEND}/jobs/http-1/ack").mock(return_value=httpx.Response(200))
        router.post(CB_URL).mock(return_value=httpx.Response(200))

        stop = threading.Event()
        t = threading.Thread(
            target=_lane_loop,
            args=("image", None, ctx, {}, stop),
            daemon=True,
        )
        t.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(poll_calls) < 2:
            time.sleep(0.05)
        stop.set()
        t.join(timeout=2.0)

    assert poll_calls, "lane should have polled the HTTP fallback"
    assert any("lane=image" in u for u in poll_calls)
