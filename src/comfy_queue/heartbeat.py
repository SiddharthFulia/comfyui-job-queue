from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from collections.abc import Callable
from typing import Any


log = logging.getLogger(__name__)


def _gpu_snapshot() -> dict[str, Any]:
    # pynvml is intentionally soft — operators that want GPU metrics install it themselves
    try:
        import pynvml  # type: ignore[import-not-found]
    except ImportError:
        return {"available": False}
    try:
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        devices: list[dict[str, Any]] = []
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            devices.append(
                {
                    "index": i,
                    "name": pynvml.nvmlDeviceGetName(h).decode() if isinstance(pynvml.nvmlDeviceGetName(h), bytes) else pynvml.nvmlDeviceGetName(h),
                    "mem_used_mb": int(mem.used / 1024 / 1024),
                    "mem_total_mb": int(mem.total / 1024 / 1024),
                    "gpu_util_pct": int(util.gpu),
                }
            )
        pynvml.nvmlShutdown()
        return {"available": True, "devices": devices}
    except Exception as e:  # pragma: no cover
        return {"available": False, "error": str(e)}


def _mem_snapshot() -> dict[str, Any]:
    total, used, free = shutil.disk_usage(os.getcwd())
    return {
        "disk_total_mb": int(total / 1024 / 1024),
        "disk_free_mb": int(free / 1024 / 1024),
        "disk_used_mb": int(used / 1024 / 1024),
    }


def build_heartbeat_payload(
    *,
    worker_name: str,
    lanes: tuple[str, ...],
    lane_state: dict[str, str],
) -> dict[str, Any]:
    return {
        "event": "heartbeat",
        "worker": worker_name,
        "lanes": list(lanes),
        "lane_state": dict(lane_state),
        "gpu": _gpu_snapshot(),
        "host": _mem_snapshot(),
        "pid": os.getpid(),
        "ts": time.time(),
    }


class Heartbeat:
    """Daemon thread that pings the callback URL every ``interval`` seconds."""

    def __init__(
        self,
        *,
        interval: float,
        worker_name: str,
        lanes: tuple[str, ...],
        lane_state: dict[str, str],
        send: Callable[[dict[str, Any]], None],
    ):
        self.interval = interval
        self.worker_name = worker_name
        self.lanes = lanes
        self.lane_state = lane_state
        self.send = send
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="hb", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.send(
                    build_heartbeat_payload(
                        worker_name=self.worker_name,
                        lanes=self.lanes,
                        lane_state=self.lane_state,
                    )
                )
            except Exception as e:  # pragma: no cover
                log.warning("heartbeat send failed: %s", e)
            # sleep in small chunks so stop() returns promptly
            stepped = 0.0
            while stepped < self.interval and not self._stop.is_set():
                time.sleep(0.5)
                stepped += 0.5
