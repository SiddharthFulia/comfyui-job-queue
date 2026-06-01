# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-01

### Added
- Initial release.
- Multi-lane worker (`video`, `image`, `lipsync`, `audio`, `mesh`) with per-lane threads.
- `BrokerHandle` over `pika` with `x-dead-letter-exchange` per lane.
- HTTP polling fallback (`BACKEND_URL/jobs/next?lane=<lane>`) when the broker is unreachable.
- `ComfyClient` with `_poll_history` and no global timeout — only an idle-progress watchdog.
- 30-second heartbeat with GPU + memory snapshot.
- Pydantic `Job` schema, handler `registry`, sample handlers for video / image / mesh.
- Callbacks: `progress`, `complete`, `failed`.
- VRAM auto-switch (`normalvram` ↔ `lowvram`) for heavy models.
- Optional sage-attention env helper.
- Examples: `run-worker.py`, `submit-job.py`, `custom-handler.py`.
- Docs: `ARCHITECTURE.md`, `RABBITMQ.md`, `HEAVY_MODELS.md`.
- CI: GitHub Actions matrix (Python 3.11, 3.12) with a real RabbitMQ service container.
