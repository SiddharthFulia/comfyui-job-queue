from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaneTopology:
    queue: str
    dlx_exchange: str
    dlq: str
    dlx_routing_key: str

    @property
    def queue_arguments(self) -> dict[str, str]:
        return {
            "x-dead-letter-exchange": self.dlx_exchange,
            "x-dead-letter-routing-key": self.dlx_routing_key,
        }


def topology_for(lane: str) -> LaneTopology:
    """Return the canonical queue/DLX names for a lane."""
    lane = lane.strip().lower()
    if not lane:
        raise ValueError("lane must be a non-empty string")
    return LaneTopology(
        queue=f"comfy.{lane}",
        dlx_exchange=f"comfy.{lane}.dlx",
        dlq=f"comfy.{lane}.dlq",
        dlx_routing_key=f"comfy.{lane}.dead",
    )


def declare_lane(channel, lane: str) -> LaneTopology:
    """Declare the queue + DLX + DLQ for a single lane on an open channel."""
    topo = topology_for(lane)

    channel.exchange_declare(
        exchange=topo.dlx_exchange,
        exchange_type="fanout",
        durable=True,
    )
    channel.queue_declare(queue=topo.dlq, durable=True)
    channel.queue_bind(queue=topo.dlq, exchange=topo.dlx_exchange)

    channel.queue_declare(
        queue=topo.queue,
        durable=True,
        arguments=dict(topo.queue_arguments),
    )
    return topo
