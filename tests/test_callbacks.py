from __future__ import annotations

import json

import httpx
import respx

from comfy_queue.callbacks import send_complete, send_failed, send_progress

CB_URL = "http://localhost:4001/api/jobs/callback"


def _payload(body: bytes) -> dict:
    """Decode the request body as JSON so assertions are independent of
    json.dumps separator formatting (httpx uses ``", "`` / ``": "``)."""
    return json.loads(body.decode("utf-8"))


@respx.mock
def test_send_progress_posts_payload():
    route = respx.post(CB_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    ok = send_progress(CB_URL, job_id="j1", progress=0.5, message="halfway")
    assert ok is True
    assert route.called
    payload = _payload(route.calls.last.request.content)
    assert payload["event"] == "progress"
    assert payload["job_id"] == "j1"


@respx.mock
def test_send_progress_clamps():
    respx.post(CB_URL).mock(return_value=httpx.Response(200))
    send_progress(CB_URL, job_id="j1", progress=5.0)
    payload = _payload(respx.calls.last.request.content)
    assert payload["progress"] == 1.0


@respx.mock
def test_send_complete_posts_outputs():
    route = respx.post(CB_URL).mock(return_value=httpx.Response(200))
    send_complete(CB_URL, job_id="abc", outputs={"files": ["a.png"]})
    assert route.called
    payload = _payload(route.calls.last.request.content)
    assert payload["event"] == "complete"
    assert payload["outputs"]["files"] == ["a.png"]


@respx.mock
def test_send_failed_includes_error_kind():
    respx.post(CB_URL).mock(return_value=httpx.Response(200))
    send_failed(CB_URL, job_id="abc", error="OOM", error_kind="OutOfMemoryError")
    payload = _payload(respx.calls.last.request.content)
    assert payload["event"] == "failed"
    assert payload["error_kind"] == "OutOfMemoryError"


@respx.mock
def test_callbacks_never_raise_on_http_error():
    respx.post(CB_URL).mock(return_value=httpx.Response(500))
    assert send_progress(CB_URL, job_id="j1", progress=0.1) is False
    assert send_complete(CB_URL, job_id="j1") is False
    assert send_failed(CB_URL, job_id="j1", error="boom") is False


@respx.mock
def test_callback_secret_header_is_forwarded():
    route = respx.post(CB_URL).mock(return_value=httpx.Response(200))
    send_progress(CB_URL, job_id="j1", progress=0.2, secret="s3cret")
    headers = route.calls.last.request.headers
    assert headers.get("x-callback-secret") == "s3cret"


@respx.mock
def test_callbacks_swallow_network_error():
    respx.post(CB_URL).mock(side_effect=httpx.ConnectError("nope"))
    assert send_progress(CB_URL, job_id="x", progress=0.1) is False
