# Contributing

Thanks for considering a contribution.

## Dev setup

```bash
git clone https://github.com/SiddharthFulia/comfyui-job-queue
cd comfyui-job-queue
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running the tests

```bash
pytest -q
```

Tests are fully mocked — no live broker, no live ComfyUI, no live backend. `respx` covers httpx, a hand-rolled `FakeChannel` covers `pika`.

## Lint

```bash
ruff check src tests
```

## Conventions

- Public API lives at the top of `src/comfy_queue/__init__.py`. If you add something, export it there or document why it stays private.
- Lane names are lowercase, singular: `video`, `image`, not `videos`.
- All callbacks are best-effort — never raise out of `callbacks.py`.
- The `ComfyClient` polling loop must not introduce a global wall-clock timeout. Long Hunyuan renders are first-class.

## Filing issues

Please include:
- Python version
- Whether you were on the broker or the HTTP fallback path
- The lane and job `kind`
- The relevant slice of `pika` / `httpx` logs

## License

By contributing you agree your work is licensed under the project's MIT license.
