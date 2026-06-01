from __future__ import annotations

import logging
import os


log = logging.getLogger(__name__)


SAGE_ENV_KEYS = ("COMFYUI_USE_SAGE_ATTENTION", "USE_SAGE_ATTENTION")


def enable_sage_attention() -> None:
    """Flip the env vars Comfy + extensions read to opt into sage-attention."""
    for key in SAGE_ENV_KEYS:
        os.environ[key] = "1"
    log.info("sage-attention env enabled (%s)", ", ".join(SAGE_ENV_KEYS))


def disable_sage_attention() -> None:
    for key in SAGE_ENV_KEYS:
        os.environ.pop(key, None)
    log.info("sage-attention env disabled")


def is_enabled() -> bool:
    return any(os.environ.get(key) == "1" for key in SAGE_ENV_KEYS)
