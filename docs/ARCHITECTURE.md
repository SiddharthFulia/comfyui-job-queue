# Architecture

## High-level flow

```
backend  ──publish──►  RabbitMQ ──basic_get──►  lane thread
   ▲                                                │
   │                                                ▼
   │                                          registry.dispatch
   │                                                │
   │                                                ▼
   │                                          comfy_client.run
   │                                                │
   │                       progress + complete       │
   └──────────────────── callbacks.py ◄──────────────┘
```

## Lane threads

`worker.run()` starts one daemon thread per entry in `LANES`. Each thread
calls `lane._lane_loop(lane_name, broker, ctx, lane_state, stop)`. The loop:

1. Tries `broker.get(lane)` first. RabbitMQ wins when it's healthy because the
   message lands on the channel within milliseconds of being published.
2. If `broker` is `None` (startup couldn't connect) or it raises
   `BrokerUnavailable` mid-loop, the lane falls back to an HTTP poll against
   `BACKEND_URL/jobs/next?lane=<lane>`.
3. Parses the body as a `Job`, dispatches it through the registry.
4. Acks (broker) or POSTs `/jobs/{id}/ack` (HTTP) on success.
5. Nacks without requeue on failure — the message lands in the lane's DLX.

The fallback exists so a brief Rabbit blip never silently drops jobs.

## Dead-letter exchanges

Each lane declares:

| Entity | Name pattern |
|---|---|
| Main queue | `comfy.<lane>` |
| DLX | `comfy.<lane>.dlx` (fanout, durable) |
| DLQ | `comfy.<lane>.dlq` (bound to DLX) |
| Main → DLX | `x-dead-letter-exchange = comfy.<lane>.dlx` |

A `basic_nack(requeue=false)` or message expiry routes the message to the
lane's DLQ. Inspecting failures in production is then just:

```bash
rabbitmqctl list_queues name messages_ready | grep comfy.video.dlq
```

A jammed video lane never spills into `comfy.audio.dlq`, so the on-call
dashboard stays readable.

## Heartbeats

A single `Heartbeat` daemon thread posts a `{event: "heartbeat", lane_state,
gpu, host, pid}` payload to `CALLBACK_URL` every `HEARTBEAT_SECONDS`. GPU info
comes from `pynvml` if it's installed, otherwise the field is `{available: false}`.

## ComfyClient `_poll_history`

There is no global wall-clock timeout. Instead the loop tracks a *signature*
(`status_str | len(messages) | len(outputs)`); if the signature changes, we
reset the idle timer. Only when nothing has changed for
`idle_timeout_seconds` do we raise `ComfyStuckError`. This is the difference
between "30-minute Hunyuan render in progress" (good) and "Comfy crashed"
(bad).

## File map

```
src/comfy_queue/
├── __init__.py
├── version.py
├── config.py            env reader
├── job.py               pydantic schema
├── registry.py          @register decorator + dispatch
├── broker.py            BrokerHandle: pika wrapper + topology
├── dlx.py               LaneTopology + declare_lane
├── comfy_client.py      ComfyClient + _poll_history
├── comfy_workflow.py    load / clone / patch helpers
├── callbacks.py         send_progress / send_complete / send_failed
├── heartbeat.py         daemon thread + GPU snapshot
├── lane.py              the _lane_loop (broker → HTTP fallback)
├── worker.py            main() — wires everything together
├── vram.py              choose_vram_mode + HEAVY_VRAM_MODELS
├── sage_attention.py    env flipper
└── handlers/
    ├── video.py
    ├── image.py
    └── mesh.py
```
