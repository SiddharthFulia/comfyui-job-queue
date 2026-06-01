from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from comfy_queue.broker import BrokerHandle, BrokerUnavailable, Delivery
from comfy_queue.callbacks import send_complete, send_failed, send_progress
from comfy_queue.job import Job, JobStatus
from comfy_queue.registry import HandlerNotFound, dispatch

log = logging.getLogger(__name__)


@dataclass
class LaneContext:
    backend_url: str
    callback_url: str
    callback_secret: str = ""
    poll_interval_seconds: float = 5.0
    # injected so tests can stub the transport
    http_client_factory: Callable[[], httpx.Client] | None = None

    def http(self) -> httpx.Client:
        if self.http_client_factory is not None:
            return self.http_client_factory()
        return httpx.Client(timeout=10.0)


def _parse_job(body: dict[str, Any], *, fallback_lane: str) -> Job:
    body = dict(body)
    body.setdefault("lane", fallback_lane)
    body.setdefault("status", JobStatus.PENDING.value)
    return Job.model_validate(body)


def _http_fetch_job(ctx: LaneContext, lane: str) -> Job | None:
    try:
        with ctx.http() as client:
            r = client.get(f"{ctx.backend_url}/jobs/next", params={"lane": lane})
        if r.status_code == 204 or not r.content:
            return None
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        log.debug("http fallback fetch failed lane=%s err=%s", lane, e)
        return None
    if not data:
        return None
    return _parse_job(data, fallback_lane=lane)


def _http_ack(ctx: LaneContext, job: Job, *, status: JobStatus) -> None:
    try:
        with ctx.http() as client:
            client.post(
                f"{ctx.backend_url}/jobs/{job.id}/ack",
                json={"status": status.value},
            )
    except httpx.HTTPError as e:
        log.debug("http ack failed job=%s err=%s", job.id, e)


def _process_job(job: Job, ctx: LaneContext, lane_state: dict[str, str]) -> dict[str, Any]:
    lane_state[job.lane] = f"running:{job.id}"
    cb_url = job.callback_url or ctx.callback_url

    def on_progress(progress: float, message: str = "") -> None:
        send_progress(
            cb_url,
            job_id=job.id,
            progress=progress,
            message=message,
            secret=ctx.callback_secret,
        )

    handler_ctx: dict[str, Any] = {
        "on_progress": on_progress,
        "callback_url": cb_url,
        "callback_secret": ctx.callback_secret,
    }

    try:
        result = dispatch(job, handler_ctx)
    except HandlerNotFound:
        send_failed(
            cb_url,
            job_id=job.id,
            error=f"no handler registered for kind={job.kind!r}",
            error_kind="handler_not_found",
            secret=ctx.callback_secret,
        )
        raise
    except Exception as e:
        send_failed(
            cb_url,
            job_id=job.id,
            error=str(e),
            error_kind=e.__class__.__name__,
            secret=ctx.callback_secret,
        )
        raise

    send_complete(cb_url, job_id=job.id, outputs=result, secret=ctx.callback_secret)
    return result


def _lane_loop(
    lane: str,
    broker: BrokerHandle | None,
    ctx: LaneContext,
    lane_state: dict[str, str],
    stop: threading.Event,
) -> None:
    lane_state[lane] = "idle"
    while not stop.is_set():
        delivery: Delivery | None = None
        job: Job | None = None
        used_broker = False

        if broker is not None:
            try:
                delivery = broker.get(lane)
                used_broker = True
            except BrokerUnavailable as e:
                log.warning("lane=%s broker unavailable, falling back to HTTP: %s", lane, e)
                broker = None  # tear down for this loop; main thread can reopen

        if delivery is not None:
            try:
                job = _parse_job(delivery.body, fallback_lane=lane)
            except Exception as e:
                log.warning("lane=%s bad job payload: %s", lane, e)
                if broker is not None:
                    broker.nack(delivery.delivery_tag, requeue=False)
                continue

        if job is None and not used_broker:
            job = _http_fetch_job(ctx, lane)

        if job is None:
            lane_state[lane] = "idle"
            _interruptible_sleep(stop, ctx.poll_interval_seconds)
            continue

        try:
            _process_job(job, ctx, lane_state)
            if delivery is not None and broker is not None:
                broker.ack(delivery.delivery_tag)
            else:
                _http_ack(ctx, job, status=JobStatus.COMPLETE)
        except Exception as e:
            log.exception("lane=%s job=%s failed: %s", lane, job.id, e)
            if delivery is not None and broker is not None:
                # don't requeue — let the DLX catch it
                broker.nack(delivery.delivery_tag, requeue=False)
            else:
                _http_ack(ctx, job, status=JobStatus.FAILED)

        lane_state[lane] = "idle"


def _interruptible_sleep(stop: threading.Event, seconds: float, step: float = 0.5) -> None:
    waited = 0.0
    while waited < seconds and not stop.is_set():
        time.sleep(step)
        waited += step
