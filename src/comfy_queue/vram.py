from __future__ import annotations

from collections.abc import Iterable

HEAVY_VRAM_MODELS: tuple[str, ...] = (
    "hunyuan",
    "wan",
    "wan2",
    "flux-dev",
    "ltx",
    "ltxv",
    "cogvideo",
    "mochi",
)


def is_heavy_model(model: str | None, *, heavy: Iterable[str] = HEAVY_VRAM_MODELS) -> bool:
    """Case-insensitive substring match against the heavy list."""
    if not model:
        return False
    needle = model.lower()
    return any(h in needle for h in heavy)


def choose_vram_mode(
    model: str | None,
    *,
    available_vram_gb: float | None = None,
    heavy: Iterable[str] = HEAVY_VRAM_MODELS,
) -> str:
    """Return ``"lowvram"`` or ``"normalvram"``."""
    if is_heavy_model(model, heavy=heavy):
        return "lowvram"
    if available_vram_gb is not None and available_vram_gb < 16:
        return "lowvram"
    return "normalvram"
