from __future__ import annotations

import logging
import signal
import sys
import threading
from typing import Any

import httpx

from comfy_queue.broker import BrokerHandle, BrokerUnavailable
from comfy_queue.config import Config, load_config
from comfy_queue.heartbeat import Heartbeat
from comfy_queue.lane import LaneContext, _lane_loop
from comfy_queue.sage_attention import enable_sage_attention

# register default handlers so ``comfy-queue-worker`` works out of the box
from comfy_queue.handlers import image as _image_handler  # noqa: F401
from comfy_queue.handlers import mesh as _mesh_handler  # noqa: F401
from comfy_queue.handlers import video as _video_handler  # noqa: F401


log = logging.getLogger(__name__)


def _open_broker(cfg: Config) -> BrokerHandle | None:
    if not cfg.rabbitmq_url:
        log.info("RABBITMQ_URL not set; running in HTTP fallback mode")
        return None
    handle = BrokerHandle(cfg.rabbitmq_url, cfg.lanes, prefetch=cfg.broker_prefetch)
    try:
        handle.open()
    except BrokerUnavailable as e:
        log.warning("broker unavailable at startup: %s — falling back to HTTP", e)
        return None
    return handle


def _heartbeat_sender(cfg: Config):
    def send(payload: dict[str, Any]) -> None:
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(cfg.callback_url, json=payload, headers={
                    "x-callback-secret": cfg.callback_secret,
                })
        except httpx.HTTPError as e:
            log.debug("heartbeat post failed: %s", e)

    return send


def run(cfg: Config | None = None) -> int:
    """Programmatic entry point. Returns a process exit code."""
    cfg = cfg or load_config()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    if cfg.sage_attention:
        enable_sage_attention()

    broker = _open_broker(cfg)
    ctx = LaneContext(
        backend_url=cfg.backend_url,
        callback_url=cfg.callback_url,
        callback_secret=cfg.callback_secret,
        poll_interval_seconds=cfg.poll_interval_seconds,
    )

    lane_state: dict[str, str] = {lane: "starting" for lane in cfg.lanes}
    stop = threading.Event()

    threads: list[threading.Thread] = []
    for lane in cfg.lanes:
        t = threading.Thread(
            target=_lane_loop,
            name=f"lane-{lane}",
            args=(lane, broker, ctx, lane_state, stop),
            daemon=True,
        )
        t.start()
        threads.append(t)

    heartbeat = Heartbeat(
        interval=cfg.heartbeat_seconds,
        worker_name=cfg.worker_name,
        lanes=cfg.lanes,
        lane_state=lane_state,
        send=_heartbeat_sender(cfg),
    )
    heartbeat.start()

    def _shutdown(signum, _frame):
        log.info("signal %d received — shutting down", signum)
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    log.info(
        "worker=%s lanes=%s broker=%s",
        cfg.worker_name,
        ",".join(cfg.lanes),
        "yes" if broker else "no (HTTP fallback)",
    )

    try:
        while not stop.is_set():
            stop.wait(timeout=1.0)
    finally:
        heartbeat.stop()
        for t in threads:
            t.join(timeout=5.0)
        if broker is not None:
            broker.close()

    log.info("worker stopped cleanly")
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
