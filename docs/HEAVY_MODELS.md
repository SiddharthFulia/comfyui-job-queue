# Heavy models — VRAM + sage-attention

## When to flip lowvram

`comfy_queue.vram.choose_vram_mode(model, available_vram_gb=None)` returns
`"lowvram"` or `"normalvram"`. The rules:

1. `model` substring matches `HEAVY_VRAM_MODELS` → `lowvram`
2. `available_vram_gb < 16` → `lowvram`
3. Otherwise → `normalvram`

Default heavy list:

```python
HEAVY_VRAM_MODELS = (
    "hunyuan", "wan", "wan2",
    "flux-dev", "ltx", "ltxv",
    "cogvideo", "mochi",
)
```

Override via `HEAVY_VRAM_MODELS=hunyuan,wan,custom-x` in your `.env`.

### How the handlers use it

The sample handlers call `choose_vram_mode(job.model)` and pass it through to
ComfyUI by either:

* Adding `--lowvram` to the Comfy launcher (if you control the launch).
* Setting a model-loader node's `weight_dtype` to `fp8_e4m3fn` or
  `fp8_e5m2` and forcing CPU-offload via the workflow.
* Switching the workflow's diffusion model node to the smaller variant
  (e.g. `hunyuan-video-720p-fp8` instead of `bf16`).

Which one is right depends on the Comfy build — `lowvram` is exposed as a
CLI flag on the upstream server.

## sage-attention

Set `SAGE_ATTENTION=1` in the worker's environment to flip the env vars
ComfyUI looks for at startup:

```
COMFYUI_USE_SAGE_ATTENTION=1
USE_SAGE_ATTENTION=1
```

If `sageattention` is installed in the Comfy Python environment, you'll see
roughly **1.5–2x** speed-up on video diffusion attention on Ampere and
newer NVIDIA cards. If it isn't installed, Comfy logs a warning and falls
back to xformers — no failure mode.

### Installing sage-attention

In your Comfy venv (not the worker venv):

```bash
pip install sageattention
```

For best results compile from source against your local CUDA:

```bash
git clone https://github.com/thu-ml/SageAttention
cd SageAttention
pip install .
```

## Tested heavy models

| Model | Lane | Notes |
|---|---|---|
| `hunyuan-video-720p-bf16` | video | Needs `lowvram` on 24 GB. ~25 min for 5s @ 720p. |
| `wan2.1-i2v-14b` | video | Heavy. Pair with sage-attention. |
| `ltxv-13b` | video | Faster than Hunyuan, still benefits from lowvram on 16 GB. |
| `flux-dev-fp8` | image | `lowvram` not strictly needed at fp8 on 16 GB+. |
| `hunyuan3d-2` | mesh | Disk-IO heavy. Make sure `COMFY_OUTPUT_DIR` is on SSD. |

## Watchdog idle timer

Long renders don't trip the watchdog because the watchdog only fires when
the history payload stops *changing*. Comfy emits new entries to
`status.messages` and `outputs` throughout a render — see
`ComfyClient._poll_history`. Tune `idle_timeout_seconds` if your model
genuinely emits nothing for long stretches (default 180s is usually fine).
