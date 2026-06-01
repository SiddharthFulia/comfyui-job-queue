from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import pika
from pika.exceptions import AMQPConnectionError, AMQPError

from comfy_queue.dlx import LaneTopology, declare_lane


log = logging.getLogger(__name__)


class BrokerUnavailable(RuntimeError):
    """Raised when the broker is unreachable; callers should fall back to HTTP."""


@dataclass
class Delivery:
    delivery_tag: int
    body: dict[str, Any]
    redelivered: bool


class BrokerHandle:
    """One connection + one channel, with lane topology already declared.

    ``open`` raises :class:`BrokerUnavailable` instead of pika exceptions so
    the caller can switch transport without catching AMQP internals.
    """

    def __init__(self, url: str, lanes: tuple[str, ...], prefetch: int = 1):
        self.url = url
        self.lanes = tuple(lanes)
        self.prefetch = prefetch
        self._conn: pika.BlockingConnection | None = None
        self._channel: Any | None = None
        self._topology: dict[str, LaneTopology] = {}

    def open(self) -> None:
        """Connect and declare every lane queue + DLX. Idempotent."""
        if self._conn is not None and self._conn.is_open:
            return
        try:
            params = pika.URLParameters(self.url)
            self._conn = pika.BlockingConnection(params)
            self._channel = self._conn.channel()
            self._channel.basic_qos(prefetch_count=self.prefetch)
            for lane in self.lanes:
                self._topology[lane] = declare_lane(self._channel, lane)
            log.info("broker open: %d lane(s) declared", len(self.lanes))
        except (AMQPConnectionError, AMQPError, OSError) as e:
            self._conn = None
            self._channel = None
            raise BrokerUnavailable(str(e)) from e

    def close(self) -> None:
        try:
            if self._channel is not None and self._channel.is_open:
                self._channel.close()
        except AMQPError:
            pass
        try:
            if self._conn is not None and self._conn.is_open:
                self._conn.close()
        except AMQPError:
            pass
        self._channel = None
        self._conn = None

    def topology(self, lane: str) -> LaneTopology:
        return self._topology[lane]

    def get(self, lane: str) -> Delivery | None:
        """Non-blocking basic_get. Returns ``None`` when the queue is empty."""
        if self._channel is None:
            raise BrokerUnavailable("channel is not open")
        topo = self._topology.get(lane)
        if topo is None:
            raise KeyError(f"lane {lane!r} not declared on this handle")
        try:
            method, _props, body = self._channel.basic_get(queue=topo.queue, auto_ack=False)
        except AMQPError as e:
            raise BrokerUnavailable(str(e)) from e
        if method is None:
            return None
        try:
            decoded = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            # nack without requeue so the DLX picks up the garbage
            self.nack(method.delivery_tag, requeue=False)
            log.warning("dropped non-JSON message on lane=%s", lane)
            return None
        return Delivery(
            delivery_tag=method.delivery_tag,
            body=decoded,
            redelivered=bool(method.redelivered),
        )

    def ack(self, delivery_tag: int) -> None:
        if self._channel is None:
            raise BrokerUnavailable("channel is not open")
        self._channel.basic_ack(delivery_tag=delivery_tag)

    def nack(self, delivery_tag: int, requeue: bool = False) -> None:
        if self._channel is None:
            raise BrokerUnavailable("channel is not open")
        self._channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)

    def publish(self, lane: str, body: dict[str, Any]) -> None:
        """Publish a job onto a lane queue."""
        if self._channel is None:
            raise BrokerUnavailable("channel is not open")
        topo = self._topology.get(lane) or declare_lane(self._channel, lane)
        self._topology.setdefault(lane, topo)
        self._channel.basic_publish(
            exchange="",
            routing_key=topo.queue,
            body=json.dumps(body).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,  # persistent
            ),
        )
