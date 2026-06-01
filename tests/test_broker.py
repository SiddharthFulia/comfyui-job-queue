from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from comfy_queue.broker import BrokerHandle, BrokerUnavailable
from comfy_queue.dlx import topology_for


@pytest.fixture
def open_handle(fake_connection):
    handle = BrokerHandle(
        "amqp://guest:guest@localhost:5672/",
        lanes=("video", "image"),
        prefetch=2,
    )
    with patch("comfy_queue.broker.pika.BlockingConnection", return_value=fake_connection):
        handle.open()
    return handle, fake_connection.channel_obj


def test_open_declares_queues_with_dlx(open_handle):
    handle, channel = open_handle
    queues = {q["queue"]: q for q in channel.declared_queues}
    assert "comfy.video" in queues
    assert "comfy.image" in queues
    assert queues["comfy.video"]["arguments"]["x-dead-letter-exchange"] == "comfy.video.dlx"
    assert queues["comfy.image"]["arguments"]["x-dead-letter-exchange"] == "comfy.image.dlx"
    assert "comfy.video.dlq" in queues
    assert "comfy.image.dlq" in queues
    assert channel.prefetch == 2


def test_get_returns_none_on_empty(open_handle):
    handle, _ = open_handle
    assert handle.get("video") is None


def test_get_decodes_json_and_carries_tag(open_handle):
    handle, channel = open_handle
    channel.push("comfy.video", {"id": "job-1", "kind": "video", "lane": "video"})

    delivery = handle.get("video")
    assert delivery is not None
    assert delivery.body["id"] == "job-1"
    assert delivery.delivery_tag == 1
    assert delivery.redelivered is False


def test_get_drops_non_json(open_handle):
    handle, channel = open_handle
    channel._messages.setdefault(
        "comfy.video",
        channel._messages.get("comfy.video") or __import__("collections").deque(),
    ).append(b"not json {{")

    delivery = handle.get("video")
    assert delivery is None
    assert channel.nacked and channel.nacked[-1][1] is False


def test_ack_and_nack(open_handle):
    handle, channel = open_handle
    channel.push("comfy.image", {"id": "job-2", "kind": "image", "lane": "image"})
    d = handle.get("image")
    handle.ack(d.delivery_tag)
    assert channel.acked == [d.delivery_tag]

    channel.push("comfy.image", {"id": "job-3", "kind": "image", "lane": "image"})
    d2 = handle.get("image")
    handle.nack(d2.delivery_tag, requeue=False)
    assert channel.nacked[-1] == (d2.delivery_tag, False)


def test_publish_serializes_and_lands_in_queue(open_handle):
    handle, channel = open_handle
    handle.publish("video", {"id": "p", "kind": "video", "lane": "video"})
    assert channel.published, "publish should have recorded a frame"
    routed = channel.published[-1]
    assert routed["routing_key"] == "comfy.video"
    parsed = json.loads(routed["body"].decode())
    assert parsed["id"] == "p"


def test_topology_lane_names_are_consistent():
    t = topology_for("video")
    assert t.queue == "comfy.video"
    assert t.dlx_exchange == "comfy.video.dlx"
    assert t.dlq == "comfy.video.dlq"
    assert t.queue_arguments["x-dead-letter-exchange"] == "comfy.video.dlx"


def test_open_raises_broker_unavailable_on_connection_failure():
    import pika.exceptions

    handle = BrokerHandle("amqp://nope:nope@localhost:9/", lanes=("video",))
    with patch(
        "comfy_queue.broker.pika.BlockingConnection",
        side_effect=pika.exceptions.AMQPConnectionError("nope"),
    ):
        with pytest.raises(BrokerUnavailable):
            handle.open()
