from __future__ import annotations

from comfy_queue.config import load_config
from comfy_queue.worker import run


if __name__ == "__main__":
    cfg = load_config()
    raise SystemExit(run(cfg))
