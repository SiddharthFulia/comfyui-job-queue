from __future__ import annotations

import logging
from typing import Any

from comfy_queue.comfy_client import ComfyClient
from comfy_queue.config import load_config
from comfy_queue.job import Job
from comfy_queue.registry import register
from comfy_queue.vram import choose_vram_mode


log = logging.getLogger(__name__)


@register("video")
def handle_video(job: Job, ctx: dict[str, Any]) -> dict[str, Any]:
    """Run a video workflow."""
    cfg = ctx.get("config") or load_config()
    workflow = job.payload.get("workflow")
    if not workflow:
        raise ValueError("video job missing payload.workflow")

    vram_mode = choose_vram_mode(job.model)
    log.info("video job=%s model=%s vram=%s", job.id, job.model, vram_mode)

    on_progress = ctx.get("on_progress")
    client = ComfyClient(cfg.comfy_host)

    def progress(entry: dict[str, Any]) -> None:
        if on_progress is None:
            return
        msgs = (entry.get("status") or {}).get("messages") or []
        if msgs:
            on_progress(0.5, f"{len(msgs)} comfy events")

    result = client.run(workflow, on_progress=progress)
    outputs = result.get("outputs") or {}
    return {"comfy": result.get("status"), "outputs": outputs, "vram_mode": vram_mode}
