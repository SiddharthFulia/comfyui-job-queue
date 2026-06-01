# comfyui-job-queue

Production-grade Python job queue for chaining [ComfyUI](https://github.com/comfyanonymous/ComfyUI) workflows. Multi-lane worker pattern, RabbitMQ instant pickup with HTTP polling fallback, per-job heartbeat + progress callbacks, dead-letter exchanges per lane.

Built for real workloads: 30+ minute Hunyuan video renders, lipsync chains, mesh export pipelines, fast image lanes. Each lane has its own broker queue, its own worker thread, and its own DLX, so a wedged video job never starves your image traffic.

```
                       ┌─────────────────────────────────┐
                       │           backend / API         │
                       │   POST /jobs   POST /callback   │
                       └──────────────┬──────────────────┘
                                      │ publish
                                      ▼
   ┌────────────────────────────────────────────────────────────┐
   │                     RabbitMQ broker                        │
   │ ┌──────┐ ┌──────┐ ┌─────────┐ ┌──────┐ ┌──────┐            │
   │ │video │ │image │ │lipsync  │ │audio │ │mesh  │  + DLX per │
   │ └──────┘ └──────┘ └─────────┘ └──────┘ └──────┘  lane      │
   └──────┬───────┬─────────┬─────────┬────────┬─────────────────┘
          │       │         │         │        │
          ▼       ▼         ▼         ▼        ▼
       ┌──────────────── worker process ──────────────────┐
       │  one lane thread per lane → registry.dispatch()  │
       │  heartbeat thread (GPU, RAM, lane state)          │
       │  HTTP fallback when broker.connect() fails        │
       └────────────────────┬─────────────────────────────┘
                            │  queue_prompt + _poll_history
                            ▼
                      ┌──────────────┐
                      │   ComfyUI    │
                      │ (long jobs)  │
                      └──────────────┘
```

## Lanes

| Lane     | Typical job kind                    | Why a dedicated lane |
|----------|-------------------------------------|---------------------|
| `video`  | Hunyuan, Wan, LTX, AnimateDiff      | 5–45 min, OOM-prone, must not block anything else |
| `image`  | Flux, SDXL, Qwen-Image              | Sub-minute, high throughput |
| `lipsync`| Wav2Lip, LatentSync                 | Mid-length, GPU + ffmpeg mix |
| `audio`  | MMAudio, F5-TTS, Suno               | CPU heavy in places |
| `mesh`   | Hunyuan3D, TripoSR                  | Disk-IO heavy, separate model load |

Each lane uses:
- a dedicated RabbitMQ queue (`comfy.<lane>`) with `x-dead-letter-exchange = comfy.<lane>.dlx`
- a dedicated DLX + DLQ so failures stay scoped
- its own lane thread inside the worker process

## Install

```bash
pip install comfyui-job-queue
```

## Run

```bash
cp .env.example .env
# edit COMFY_HOST, RABBITMQ_URL, BACKEND_URL, CALLBACK_URL ...
comfy-queue-worker
```

Or as a module:

```bash
python -m comfy_queue.worker
```

## .env

See [`.env.example`](.env.example) — only `COMFY_HOST` and `CALLBACK_URL` are required for the simplest setup. `RABBITMQ_URL` is optional; if it cannot be reached, the worker falls back to polling `BACKEND_URL/jobs/next?lane=<lane>` every `POLL_INTERVAL_SECONDS`.

## Register custom handlers

```python
from comfy_queue.registry import register
from comfy_queue.job import Job

@register("my-custom-kind")
def handle(job: Job, ctx):
    # build a Comfy workflow dict, push it, return the output paths
    return {"outputs": [...]}
```

See [`examples/custom-handler.py`](examples/custom-handler.py).

## Architecture deep-dive

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — lane / DLX / fallback flow
- [`docs/RABBITMQ.md`](docs/RABBITMQ.md) — broker setup + queue topology
- [`docs/HEAVY_MODELS.md`](docs/HEAVY_MODELS.md) — when to flip lowvram, sage-attention

## License

MIT — see [LICENSE](LICENSE).
