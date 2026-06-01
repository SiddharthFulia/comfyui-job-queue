from __future__ import annotations

import pytest

from comfy_queue.vram import HEAVY_VRAM_MODELS, choose_vram_mode, is_heavy_model


@pytest.mark.parametrize(
    "model,expected",
    [
        ("hunyuan-video-720p", True),
        ("Hunyuan", True),
        ("wan2.1-i2v", True),
        ("flux-dev-fp8", True),
        ("ltxv-13b", True),
        ("sdxl-base", False),
        ("flux-schnell", False),
        ("", False),
        (None, False),
    ],
)
def test_is_heavy_model(model, expected):
    assert is_heavy_model(model) is expected


def test_choose_vram_mode_heavy_model_forces_lowvram():
    assert choose_vram_mode("hunyuan-video") == "lowvram"


def test_choose_vram_mode_small_card_forces_lowvram():
    assert choose_vram_mode("sdxl-base", available_vram_gb=12) == "lowvram"


def test_choose_vram_mode_normal_when_safe():
    assert choose_vram_mode("sdxl-base", available_vram_gb=24) == "normalvram"


def test_heavy_set_is_non_empty_tuple():
    assert isinstance(HEAVY_VRAM_MODELS, tuple)
    assert "hunyuan" in HEAVY_VRAM_MODELS
