from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakeMethod:
    delivery_tag: int
    redelivered: bool = False


@dataclass
class FakeChannel:
    """Just enough surface area to satisfy BrokerHandle in tests."""

    is_open: bool = True
    declared_exchanges: list[dict[str, Any]] = field(default_factory=list)
    declared_queues: list[dict[str, Any]] = field(default_factory=list)
    bindings: list[dict[str, Any]] = field(default_factory=list)
    published: list[dict[str, Any]] = field(default_factory=list)
    acked: list[int] = field(default_factory=list)
    nacked: list[tuple[int, bool]] = field(default_factory=list)
    _messages: dict[str, deque[bytes]] = field(default_factory=dict)
    _next_tag: int = 0
    prefetch: int | None = None

    def basic_qos(self, prefetch_count: int) -> None:
        self.prefetch = prefetch_count

    def exchange_declare(self, exchange: str, exchange_type: str, durable: bool = False, **kw):
        self.declared_exchanges.append(
            {"exchange": exchange, "type": exchange_type, "durable": durable, **kw}
        )

    def queue_declare(self, queue: str, durable: bool = False, arguments=None, **kw):
        self.declared_queues.append(
            {"queue": queue, "durable": durable, "arguments": dict(arguments or {}), **kw}
        )
        self._messages.setdefault(queue, deque())

    def queue_bind(self, queue: str, exchange: str, routing_key: str = "", **kw):
        self.bindings.append({"queue": queue, "exchange": exchange, "routing_key": routing_key})

    def push(self, queue: str, body: dict[str, Any]) -> None:
        self._messages.setdefault(queue, deque()).append(json.dumps(body).encode("utf-8"))

    def basic_get(self, queue: str, auto_ack: bool = False):
        q = self._messages.get(queue) or deque()
        if not q:
            return (None, None, None)
        body = q.popleft()
        self._next_tag += 1
        return (FakeMethod(delivery_tag=self._next_tag), None, body)

    def basic_publish(self, exchange: str, routing_key: str, body: bytes, properties=None):
        self.published.append({"exchange": exchange, "routing_key": routing_key, "body": body})
        # echo into in-memory queue so subsequent gets see it
        self._messages.setdefault(routing_key, deque()).append(body)

    def basic_ack(self, delivery_tag: int) -> None:
        self.acked.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, requeue: bool = False) -> None:
        self.nacked.append((delivery_tag, requeue))

    def close(self) -> None:
        self.is_open = False


@dataclass
class FakeConnection:
    is_open: bool = True
    channel_obj: FakeChannel = field(default_factory=FakeChannel)

    def channel(self) -> FakeChannel:
        return self.channel_obj

    def close(self) -> None:
        self.is_open = False
        self.channel_obj.close()


@pytest.fixture
def fake_channel() -> FakeChannel:
    return FakeChannel()


@pytest.fixture
def fake_connection(fake_channel) -> FakeConnection:
    return FakeConnection(channel_obj=fake_channel)


@pytest.fixture(autouse=True)
def _reset_registry():
    # NB: we import the submodule explicitly via importlib because
    # ``comfy_queue/__init__.py`` re-exports the ``registry`` dict under the
    # same attribute name, which shadows the submodule on the package object.
    # A plain ``from comfy_queue import registry as reg`` would therefore hand
    # us the dict, not the module.
    import importlib

    reg = importlib.import_module("comfy_queue.registry")

    # snapshot + restore so handler registration in tests doesn't leak
    snapshot = dict(reg.registry)
    yield
    reg.registry.clear()
    reg.registry.update(snapshot)
