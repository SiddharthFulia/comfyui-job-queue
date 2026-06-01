from __future__ import annotations

import logging
from typing import Any

import httpx


log = logging.getLogger(__name__)


# best-effort: callbacks must never raise out of this module
def _post(url: str, payload: dict[str, Any], secret: str = "", timeout: float = 10.0) -> bool:
    headers = {"content-type": "application/json"}
    if secret:
        headers["x-callback-secret"] = secret
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return True
    except httpx.HTTPError as e:
        log.warning("callback failed url=%s err=%s", url, e)
        return False


def send_progress(
    url: str,
    *,
    job_id: str,
    progress: float,
    message: str = "",
    extra: dict[str, Any] | None = None,
    secret: str = "",
) -> bool:
    payload = {
        "event": "progress",
        "job_id": job_id,
        "progress": max(0.0, min(1.0, float(progress))),
        "message": message,
    }
    if extra:
        payload.update(extra)
    return _post(url, payload, secret=secret)


def send_complete(
    url: str,
    *,
    job_id: str,
    outputs: dict[str, Any] | None = None,
    secret: str = "",
) -> bool:
    payload = {
        "event": "complete",
        "job_id": job_id,
        "outputs": outputs or {},
    }
    return _post(url, payload, secret=secret)


def send_failed(
    url: str,
    *,
    job_id: str,
    error: str,
    error_kind: str = "unknown",
    secret: str = "",
) -> bool:
    payload = {
        "event": "failed",
        "job_id": job_id,
        "error": error,
        "error_kind": error_kind,
    }
    return _post(url, payload, secret=secret)
