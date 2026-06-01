# RabbitMQ setup

## Docker

```bash
docker run -d --name comfy-rabbit \
  -p 5672:5672 -p 15672:15672 \
  rabbitmq:3.13-management-alpine
```

Management UI at `http://localhost:15672` (guest / guest by default).

## Connection URL

```
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

For TLS use `amqps://...` and make sure your Python install trusts the broker
cert.

## Queue topology

The worker declares everything it needs at startup — you don't have to
pre-create anything. For each `LANE` in your config we make:

| Entity | Name | Properties |
|---|---|---|
| Main queue | `comfy.<lane>` | `durable=true`, `x-dead-letter-exchange=comfy.<lane>.dlx`, `x-dead-letter-routing-key=comfy.<lane>.dead` |
| DLX | `comfy.<lane>.dlx` | `fanout`, `durable=true` |
| DLQ | `comfy.<lane>.dlq` | `durable=true`, bound to the DLX |

If you change `LANES` (say, add `style-transfer`), the new lane's topology is
declared on the next worker restart. Removing a lane does **not** clean up
the old queues; do that manually with `rabbitmqctl delete_queue` if you care.

## x-dead-letter-exchange notes

* `requeue=false` on `basic_nack` is what triggers a dead-letter. Our worker
  always nacks without requeue on handler failure — retries are the
  backend's job, not the worker's.
* Messages that exceed `x-message-ttl` (we don't set one — set it on the
  backend if you want stale-after behaviour) also DLX.
* The DLX is a fanout, so we only need one DLQ per lane. If you want
  routing-key-aware DLQs (e.g. one per `kind`), switch the DLX type to
  `topic` in `dlx.declare_lane`.

## Publishing jobs

The worker is a consumer; the *backend* is the publisher. Sample publisher:

```python
from comfy_queue.broker import BrokerHandle

handle = BrokerHandle("amqp://guest:guest@localhost:5672/", lanes=("image",))
handle.open()
handle.publish("image", {
    "id": "job-1",
    "kind": "image",
    "lane": "image",
    "prompt": "a fox in a snowy forest",
    "payload": {"workflow": {...}},
})
```

## Prefetch

`BROKER_PREFETCH=1` is the right default: one in-flight job per lane thread
keeps memory predictable and avoids prefetched jobs being held hostage if a
heavy render takes 30 minutes.

## Down? No problem

If `RABBITMQ_URL` is unset, unreachable, or the channel drops mid-loop, every
lane silently falls back to polling `BACKEND_URL/jobs/next?lane=<lane>` every
`POLL_INTERVAL_SECONDS`. You'll see this in the logs:

```
WARNING comfy_queue.lane :: lane=video broker unavailable, falling back to HTTP
```
