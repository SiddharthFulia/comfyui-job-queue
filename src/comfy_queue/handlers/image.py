from __future__ import annotations

import logging
from typing import Any

from comfy_queue.comfy_client import ComfyClient
from comfy_queue.comfy_workflow import randomize_seeds, set_prompt
from comfy_queue.config import load_config
from comfy_queue.job import Job
from comfy_queue.registry import register

log = logging.getLogger(__name__)


@register("image")
def handle_image(job: Job, ctx: dict[str, Any]) -> dict[str, Any]:
    """Patch the workflow's prompt + seeds, run it, return outputs."""
    cfg = ctx.get("config") or load_config()

    workflow = job.payload.get("workflow")
    if not workflow:
        raise ValueError("image job missing payload.workflow")

    if job.prompt:
        workflow = set_prompt(workflow, job.prompt)
    if job.payload.get("randomize_seeds", True):
        workflow = randomize_seeds(workflow)

    on_progress = ctx.get("on_progress")
    client = ComfyClient(cfg.comfy_host)

    def progress(entry: dict[str, Any]) -> None:
        if on_progress is None:
            return
        outs = entry.get("outputs") or {}
        on_progress(min(0.9, 0.1 + 0.1 * len(outs)), f"{len(outs)} nodes produced output")

    log.info("image job=%s prompt=%r", job.id, (job.prompt or "")[:80])
    result = client.run(workflow, on_progress=progress)
    return {"outputs": result.get("outputs") or {}}
