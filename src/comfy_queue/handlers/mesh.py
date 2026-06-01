from __future__ import annotations

import logging
from typing import Any

from comfy_queue.comfy_client import ComfyClient
from comfy_queue.config import load_config
from comfy_queue.job import Job
from comfy_queue.registry import register
from comfy_queue.vram import choose_vram_mode


log = logging.getLogger(__name__)


@register("mesh")
def handle_mesh(job: Job, ctx: dict[str, Any]) -> dict[str, Any]:
    """Run a mesh workflow and report the produced .glb / .obj paths."""
    cfg = ctx.get("config") or load_config()
    workflow = job.payload.get("workflow")
    if not workflow:
        raise ValueError("mesh job missing payload.workflow")

    vram_mode = choose_vram_mode(job.model)
    log.info("mesh job=%s model=%s vram=%s", job.id, job.model, vram_mode)

    on_progress = ctx.get("on_progress")
    client = ComfyClient(cfg.comfy_host)

    def progress(entry: dict[str, Any]) -> None:
        if on_progress is None:
            return
        on_progress(0.6, "mesh extraction in flight")

    result = client.run(workflow, on_progress=progress)
    outputs = result.get("outputs") or {}

    files: list[str] = []
    for node_outputs in outputs.values():
        for k in ("gltf", "mesh", "glb", "obj"):
            for entry in (node_outputs.get(k) or []):
                files.append(entry.get("filename") if isinstance(entry, dict) else str(entry))
    return {"outputs": outputs, "mesh_files": files, "vram_mode": vram_mode}
