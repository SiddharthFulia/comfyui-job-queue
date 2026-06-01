from __future__ import annotations

import os
from dataclasses import dataclass, field


DEFAULT_LANES = ("video", "image", "lipsync", "audio", "mesh")


def _csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    return tuple(p.strip() for p in value.split(",") if p.strip())


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    comfy_host: str = "http://127.0.0.1:8188"
    comfy_output_dir: str = "./output"

    rabbitmq_url: str | None = None
    broker_prefetch: int = 1

    backend_url: str = "http://localhost:4001/api"
    poll_interval_seconds: float = 5.0

    callback_url: str = "http://localhost:4001/api/jobs/callback"
    callback_secret: str = ""

    worker_name: str = "worker-1"
    lanes: tuple[str, ...] = field(default_factory=lambda: DEFAULT_LANES)
    heartbeat_seconds: float = 30.0

    heavy_vram_models: tuple[str, ...] = ("hunyuan", "wan", "flux-dev", "ltx")
    sage_attention: bool = False


def load_config(env: dict[str, str] | None = None) -> Config:
    """Build a Config from a mapping (defaults to os.environ)."""
    e = env if env is not None else os.environ

    return Config(
        comfy_host=e.get("COMFY_HOST", "http://127.0.0.1:8188").rstrip("/"),
        comfy_output_dir=e.get("COMFY_OUTPUT_DIR", "./output"),
        rabbitmq_url=e.get("RABBITMQ_URL") or None,
        broker_prefetch=int(e.get("BROKER_PREFETCH", "1")),
        backend_url=e.get("BACKEND_URL", "http://localhost:4001/api").rstrip("/"),
        poll_interval_seconds=float(e.get("POLL_INTERVAL_SECONDS", "5")),
        callback_url=e.get("CALLBACK_URL", "http://localhost:4001/api/jobs/callback"),
        callback_secret=e.get("CALLBACK_SECRET", ""),
        worker_name=e.get("WORKER_NAME", "worker-1"),
        lanes=_csv(e.get("LANES", ""), DEFAULT_LANES),
        heartbeat_seconds=float(e.get("HEARTBEAT_SECONDS", "30")),
        heavy_vram_models=_csv(e.get("HEAVY_VRAM_MODELS", ""), ("hunyuan", "wan", "flux-dev", "ltx")),
        sage_attention=_bool(e.get("SAGE_ATTENTION"), default=False),
    )
