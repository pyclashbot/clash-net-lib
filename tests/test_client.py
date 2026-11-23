from __future__ import annotations

import base64
import json
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
from websockets.sync.server import serve

from clashnet.client import (
    Client,
    ClientNotConnected,
    ClientTimeout,
    ServerError,
    build_frame,
    build_hello,
    chunk_text,
    connect,
    decide,
    infer,
)
from clashnet.validate import validate_envelope

CAPABILITIES = {
    "vision": True,
    "play": True,
    "actions": ["deploy", "none", "ability"],
    "state_schema": "1.2",
    "retention": {"requires_consent": True},
}

PLAY = {
    "type": "deploy",
    "slot": 0,
    "xy_norm": [0.5, 0.5],
    "xy_px": [208, 267],
    "game_s": 1.0,
    "source": "test",
}

STATE = {
    "schema_version": "1.2",
    "in_fight": True,
    "image_size": [419, 633],
    "units": [],
    "hand_cards": [],
    "towers": {
        "enemy_left": {"status": "unknown"},
        "enemy_right": {"status": "unknown"},
        "enemy_main": {"status": "unknown"},
        "friendly_left": {"status": "unknown"},
        "friendly_right": {"status": "unknown"},
        "friendly_main": {"status": "unknown"},
    },
}


def responder(message: dict[str, Any]) -> list[dict[str, Any]]:
    if message.get("type") == "hello":
        return [{"v": "0.1", "type": "hello_ack", "capabilities": CAPABILITIES}]
    if message.get("type") != "frame":
        return []
    responses = []
    want = message.get("want", [])
    if "state" in want:
        responses.append({"v": "0.1", "type": "state", "seq": message["seq"], "state": STATE})
    if "play" in want:
        responses.append(
            {
                "v": "0.1",
                "type": "play",
                "seq": message["seq"],
                "play": PLAY,
                "playable": [0],
            }
        )
    return responses


@contextmanager
def serve_script(
    script: Any = responder,
) -> Generator[tuple[str, list[dict[str, Any]]], None, None]:
    received: list[dict[str, Any]] = []

    def handler(connection: Any) -> None:
        try:
            for raw in connection:
                message = json.loads(raw)
                received.append(message)
                for response in script(message):
                    connection.send(json.dumps(response))
        except Exception:
            pass

    server = serve(handler, host="127.0.0.1", port=0)
    port = server.socket.getsockname()[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"ws://127.0.0.1:{port}", received
    finally:
        server.shutdown()
        thread.join(timeout=2)


def collect(client: Client, count: int, timeout: float = 2.0) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    messages: list[dict[str, Any]] = []
    while len(messages) < count and time.monotonic() < deadline:
        messages.extend(cast_list(client.drain()))
        if len(messages) < count:
            time.sleep(0.01)
    return messages


def cast_list(messages: list[Any]) -> list[dict[str, Any]]:
    return [message for message in messages if isinstance(message, dict)]


def test_build_hello_and_frame_validate() -> None:
    hello = build_hello(session_id="session")
    validate_envelope(hello)

    frame = build_frame(
        session_id="session",
        seq=1,
        image=b"jpeg",
        w=419,
        h=633,
        consent_training=True,
    )
    validate_envelope(frame)
    assert frame["image"]["b64"] == base64.b64encode(b"jpeg").decode("ascii")
    assert frame["consent"] == {"training": True}


def test_build_frame_rejects_empty_image() -> None:
    with pytest.raises(ValueError):
        build_frame(session_id="s", seq=1, image=b"", w=1, h=1)


def test_chunk_text() -> None:
    assert [len(part) for part in chunk_text("a" * 70_000, 30_000)] == [
        30_000,
        30_000,
        10_000,
    ]
    with pytest.raises(ValueError):
        chunk_text("x", 0)


def test_core_import_does_not_load_websockets() -> None:
    subprocess.run(
        [sys.executable, "-c", "import sys, clashnet; assert 'websockets' not in sys.modules"],
        check=True,
    )


def test_client_handshake() -> None:
    with serve_script() as (url, _), Client(url) as client:
        assert client.connected
        assert client.capabilities == CAPABILITIES


def test_client_infer() -> None:
    with serve_script() as (url, received):
        with Client(url) as client:
            message = client.infer(b"jpeg", w=419, h=633)
            assert message["type"] == "state"
            assert message["state"]["schema_version"] == "1.2"
        frame = [item for item in received if item["type"] == "frame"][-1]
        assert frame["want"] == ["state"]
        assert "consent" not in frame


def test_client_decide_sends_consent() -> None:
    with serve_script() as (url, received):
        with Client(url, consent_training=True) as client:
            message = client.decide(b"jpeg", w=419, h=633)
            assert message["type"] == "play"
        frame = [item for item in received if item["type"] == "frame"][-1]
        assert frame["want"] == ["play"]
        assert frame["consent"] == {"training": True}


def test_client_poll_returns_newest() -> None:
    with serve_script() as (url, _), Client(url) as client:
        client.send_frame(b"jpeg", w=419, h=633, seq=7)
        messages = collect(client, 2)
        assert [item["type"] for item in messages] == ["state", "play"]

        client.send_frame(b"jpeg", w=419, h=633, seq=8)
        deadline = time.monotonic() + 2.0
        while client.pending < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        newest = client.poll()
        assert newest is not None
        assert newest["type"] == "play"
        assert newest["seq"] == 8


def test_client_fragmented_frame() -> None:
    with serve_script() as (url, received):
        with Client(url, max_frame_bytes=30_000) as client:
            client.decide(b"x" * 40_000, w=419, h=633)
        frame = [item for item in received if item["type"] == "frame"][-1]
        assert len(frame["image"]["b64"]) > 50_000


def test_client_server_error() -> None:
    def script(message: dict[str, Any]) -> list[dict[str, Any]]:
        if message.get("type") == "hello":
            return [{"v": "0.1", "type": "hello_ack", "capabilities": CAPABILITIES}]
        return [
            {
                "v": "0.1",
                "type": "error",
                "seq": message.get("seq"),
                "error": {"code": "bad_frame", "message": "nope"},
            }
        ]

    with serve_script(script) as (url, _), Client(url) as client:
        with pytest.raises(ServerError) as caught:
            client.decide(b"jpeg", w=419, h=633, timeout=2.0)
        assert caught.value.code == "bad_frame"


def test_client_request_timeout() -> None:
    def script(message: dict[str, Any]) -> list[dict[str, Any]]:
        if message.get("type") == "hello":
            return [{"v": "0.1", "type": "hello_ack", "capabilities": CAPABILITIES}]
        return []

    with serve_script(script) as (url, _), Client(url) as client, pytest.raises(ClientTimeout):
        client.decide(b"jpeg", w=419, h=633, timeout=0.2)


def test_send_frame_before_connect() -> None:
    client = Client("ws://127.0.0.1:1")
    with pytest.raises(ClientNotConnected):
        client.send_frame(b"jpeg", w=419, h=633, seq=1)
    client.close()


def test_connect_helper() -> None:
    with serve_script() as (url, _):
        client = connect(url)
        try:
            assert client.connected
            assert client.capabilities == CAPABILITIES
        finally:
            client.close()


def test_infer_helper() -> None:
    with serve_script() as (url, received):
        message = infer(url, b"jpeg", w=419, h=633)
        assert message["type"] == "state"
        frame = [item for item in received if item["type"] == "frame"][-1]
        assert frame["want"] == ["state"]


def test_decide_helper_with_consent() -> None:
    with serve_script() as (url, received):
        message = decide(url, b"jpeg", w=419, h=633, consent_training=True)
        assert message["type"] == "play"
        frame = [item for item in received if item["type"] == "frame"][-1]
        assert frame["want"] == ["play"]
        assert frame["consent"] == {"training": True}
