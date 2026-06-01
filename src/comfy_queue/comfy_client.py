from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx


log = logging.getLogger(__name__)


class ComfyJobFailed(RuntimeError):
    """Comfy reported the prompt as errored."""


class ComfyStuckError(TimeoutError):
    """No history progress in idle_timeout_seconds — likely wedged."""


@dataclass
class PollState:
    last_change_at: float
    last_signature: str


class ComfyClient:
    """Minimal HTTP client around the ComfyUI server."""

    def __init__(
        self,
        host: str,
        *,
        client: httpx.Client | None = None,
        poll_interval_seconds: float = 2.0,
        idle_timeout_seconds: float = 180.0,
    ):
        self.host = host.rstrip("/")
        # infinite read timeout — long Hunyuan jobs are first-class
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=None))
        self.poll_interval_seconds = poll_interval_seconds
        self.idle_timeout_seconds = idle_timeout_seconds

    def queue_prompt(self, workflow: dict[str, Any], *, client_id: str | None = None) -> str:
        """Submit a workflow. Returns the Comfy prompt_id."""
        body: dict[str, Any] = {"prompt": workflow}
        if client_id:
            body["client_id"] = client_id
        r = self._client.post(f"{self.host}/prompt", json=body)
        r.raise_for_status()
        data = r.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyJobFailed(f"comfy /prompt did not return prompt_id: {data!r}")
        return prompt_id

    def history(self, prompt_id: str) -> dict[str, Any]:
        r = self._client.get(f"{self.host}/history/{prompt_id}")
        r.raise_for_status()
        return r.json()

    def fetch_output(self, filename: str, *, subfolder: str = "", type_: str = "output") -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": type_}
        r = self._client.get(f"{self.host}/view", params=params)
        r.raise_for_status()
        return r.content

    def _poll_history(
        self,
        prompt_id: str,
        *,
        on_progress=None,
    ) -> dict[str, Any]:
        # no wall-clock timeout — only an idle-progress watchdog so 30-min renders survive
        state = PollState(last_change_at=time.monotonic(), last_signature="")

        while True:
            hist = self.history(prompt_id)
            entry = hist.get(prompt_id)
            sig = _signature(entry)

            if sig != state.last_signature:
                state.last_signature = sig
                state.last_change_at = time.monotonic()
                if on_progress is not None:
                    on_progress(entry or {})

            if entry is not None and _is_terminal(entry):
                status = (entry.get("status") or {}).get("status_str")
                if status == "error":
                    raise ComfyJobFailed(_extract_error(entry))
                return entry

            if time.monotonic() - state.last_change_at > self.idle_timeout_seconds:
                raise ComfyStuckError(
                    f"no progress for {self.idle_timeout_seconds:.0f}s on prompt {prompt_id}"
                )

            time.sleep(self.poll_interval_seconds)

    def run(self, workflow: dict[str, Any], *, on_progress=None) -> dict[str, Any]:
        """Queue a workflow and poll until terminal."""
        prompt_id = self.queue_prompt(workflow)
        return self._poll_history(prompt_id, on_progress=on_progress)


def _is_terminal(entry: dict[str, Any]) -> bool:
    status = (entry.get("status") or {}).get("status_str")
    if status in {"success", "error"}:
        return True
    # older Comfy builds set ``completed`` instead of status_str
    return bool((entry.get("status") or {}).get("completed"))


def _signature(entry: dict[str, Any] | None) -> str:
    if not entry:
        return ""
    status = entry.get("status") or {}
    msgs = status.get("messages") or []
    outputs = entry.get("outputs") or {}
    return f"{status.get('status_str')}|{len(msgs)}|{len(outputs)}"


def _extract_error(entry: dict[str, Any]) -> str:
    msgs = (entry.get("status") or {}).get("messages") or []
    for kind, payload in msgs:
        if kind in {"execution_error", "execution_interrupted"}:
            return str(payload)
    return "comfy reported an error with no detail"
