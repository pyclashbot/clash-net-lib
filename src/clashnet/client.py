"""Reference WebSocket binding for the Clash Net Protocol.

The core ``clashnet`` package is shape-only. This module is the optional reference
transport: install ``clash-net-lib[client]`` to use it. It requires ``websockets`` only
when a connection is opened, so ``import clashnet`` never pulls in a transport.

The client is synchronous and built for a game loop:

- ``send_frame()`` is non-blocking; frames go into a small bounded queue.
- ``poll()`` / ``drain()`` return server messages without blocking.
- ``request()`` / ``infer()`` / ``decide()`` are blocking conveniences for scripts/tests.
- A single worker thread owns the connection, hello handshake, sends, and receives.
- Reconnects with backoff and re-sends ``hello``.
"""

from __future__ import annotations

import base64
import contextlib
import itertools
import json
import threading
import time
import uuid
from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from .types import (
    Capabilities,
    FrameMessage,
    HelloMessage,
    ImageFormat,
    PlayMessage,
    ServerMessage,
    StateMessage,
)
from .version import CONTRACT_VERSION, PROTOCOL_VERSION

__all__ = [
    "Client",
    "ClientError",
    "ClientNotConnected",
    "ClientTimeout",
    "ServerError",
    "build_frame",
    "build_hello",
    "chunk_text",
]


class ClientError(RuntimeError):
    """Base client error."""


class ClientNotConnected(ClientError):
    """Raised when a streaming operation is used before ``connect()``."""


class ClientTimeout(ClientError):
    """Raised when a handshake or response does not arrive in time."""


class ServerError(ClientError):
    """Raised when the server returns an ``error`` message for a request."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def build_hello(
    *,
    session_id: str,
    client_name: str = "clashnet-client",
    client_version: str = CONTRACT_VERSION,
) -> HelloMessage:
    """Build a valid ``hello`` message."""
    return {
        "v": PROTOCOL_VERSION,
        "type": "hello",
        "session_id": session_id,
        "client": {"name": client_name, "version": client_version},
    }


def build_frame(
    *,
    session_id: str,
    seq: int,
    image: bytes,
    w: int,
    h: int,
    image_format: ImageFormat = "jpeg",
    frame_ts: int | None = None,
    fight_id: str | None = None,
    want: Sequence[Literal["state", "play"]] = ("state", "play"),
    consent_training: bool | None = None,
) -> FrameMessage:
    """Build a valid ``frame`` message. ``image`` is already encoded bytes."""
    if not image:
        raise ValueError("image is empty")
    if w <= 0 or h <= 0:
        raise ValueError("image dimensions must be positive")
    message: FrameMessage = {
        "v": PROTOCOL_VERSION,
        "type": "frame",
        "session_id": session_id,
        "seq": int(seq),
        "image": {
            "b64": base64.b64encode(image).decode("ascii"),
            "format": image_format,
            "w": int(w),
            "h": int(h),
        },
        "want": list(want),
    }
    if frame_ts is not None:
        message["frame_ts"] = int(frame_ts)
    if fight_id is not None:
        message["fight_id"] = fight_id
    if consent_training is not None:
        message["consent"] = {"training": bool(consent_training)}
    return message


def chunk_text(text: str, size: int) -> list[str]:
    """Split a JSON string into WebSocket fragments of at most ``size`` characters.

    ``json.dumps(..., ensure_ascii=True)`` keeps the payload ASCII, so splitting at any
    character boundary is safe.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    return [text[index : index + size] for index in range(0, len(text), size)]


class Client:
    """Synchronous CNP WebSocket client with a streaming and a request API."""

    def __init__(
        self,
        url: str,
        *,
        session_id: str | None = None,
        consent_training: bool | None = None,
        client_name: str = "clashnet-client",
        client_version: str = CONTRACT_VERSION,
        connect_timeout: float = 10.0,
        request_timeout: float = 10.0,
        max_frame_bytes: int = 30_000,
        reconnect: bool = True,
    ) -> None:
        if not url:
            raise ValueError("url is required")
        if max_frame_bytes < 1024:
            raise ValueError("max_frame_bytes must be at least 1024")
        self.url = url
        self.session_id = session_id or uuid.uuid4().hex
        self.consent_training = consent_training
        self.client_name = client_name
        self.client_version = client_version
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.max_frame_bytes = max_frame_bytes
        self.reconnect = reconnect

        self._stop = threading.Event()
        self._cv = threading.Condition()
        self._tx: deque[Mapping[str, Any]] = deque(maxlen=2)
        self._rx: deque[dict[str, Any]] = deque(maxlen=64)
        self._thread: threading.Thread | None = None
        self._conn: Any = None
        self._capabilities: Capabilities | None = None
        self._fatal: ClientError | None = None
        self._last_error: str | None = None
        self._seq = itertools.count(1)

    def __enter__(self) -> Client:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def capabilities(self) -> Capabilities | None:
        """Capabilities from the latest ``hello_ack``."""
        return self._capabilities

    @property
    def connected(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._capabilities is not None
        )

    @property
    def last_error(self) -> str | None:
        """Last transport error observed by the worker (for status messages)."""
        return self._last_error

    @property
    def pending(self) -> int:
        """Number of queued server messages."""
        with self._cv:
            return len(self._rx)

    def connect(self) -> Capabilities:
        """Open the socket and wait for ``hello_ack``."""
        if self._thread is not None and self._thread.is_alive():
            raise ClientError("client is already connected")
        self._stop.clear()
        self._fatal = None
        self._capabilities = None
        self._thread = threading.Thread(target=self._run, name="clashnet-client", daemon=True)
        self._thread.start()

        deadline = time.monotonic() + self.connect_timeout
        timed_out = False
        fatal: ClientError | None = None
        with self._cv:
            while self._capabilities is None:
                if self._fatal is not None:
                    fatal = self._fatal
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                self._cv.wait(remaining)
            if self._capabilities is not None:
                return self._capabilities

        self.close()
        if fatal is not None:
            raise fatal
        if timed_out:
            raise ClientTimeout("timed out waiting for hello_ack")
        raise ClientError("connection closed before hello_ack")

    def close(self) -> None:
        """Stop the worker and close the socket. Idempotent."""
        self._stop.set()
        with self._cv:
            self._cv.notify_all()
        connection = self._conn
        if connection is not None:
            with contextlib.suppress(Exception):
                connection.close()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)
            self._thread = None
        self._conn = None

    def send_frame(
        self,
        image: bytes,
        *,
        w: int,
        h: int,
        seq: int,
        image_format: ImageFormat = "jpeg",
        frame_ts: int | None = None,
        fight_id: str | None = None,
        want: Sequence[Literal["state", "play"]] = ("state", "play"),
        consent_training: bool | None = None,
    ) -> None:
        """Queue a frame. Non-blocking; the oldest queued frame is dropped under pressure."""
        if not self.connected:
            raise ClientNotConnected("call connect() before send_frame()")
        consent = self.consent_training if consent_training is None else consent_training
        message = build_frame(
            session_id=self.session_id,
            seq=seq,
            image=image,
            w=w,
            h=h,
            image_format=image_format,
            frame_ts=frame_ts,
            fight_id=fight_id,
            want=want,
            consent_training=consent,
        )
        with self._cv:
            if len(self._tx) == self._tx.maxlen:
                self._tx.popleft()
            self._tx.append(message)
            self._cv.notify_all()

    def poll(self, timeout: float = 0.0) -> ServerMessage | None:
        """Return the newest queued server message, discarding older ones."""
        deadline = time.monotonic() + max(timeout, 0.0)
        with self._cv:
            while not self._rx:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cv.wait(remaining)
            newest = self._rx.pop()
            self._rx.clear()
            return cast(ServerMessage, newest)

    def drain(self) -> list[ServerMessage]:
        """Return and clear all queued server messages in arrival order."""
        with self._cv:
            messages = list(self._rx)
            self._rx.clear()
            return cast(list[ServerMessage], messages)

    def request(
        self,
        image: bytes,
        *,
        w: int,
        h: int,
        seq: int | None = None,
        want: Sequence[Literal["state", "play"]] = ("state",),
        timeout: float | None = None,
        **kwargs: Any,
    ) -> ServerMessage:
        """Send one frame and wait for the matching response."""
        if not self.connected:
            self.connect()
        request_seq = next(self._seq) if seq is None else int(seq)
        self.send_frame(image, w=w, h=h, seq=request_seq, want=want, **kwargs)
        return self._wait_for(
            request_seq,
            set(want),
            self.request_timeout if timeout is None else timeout,
        )

    def infer(
        self,
        image: bytes,
        *,
        w: int,
        h: int,
        seq: int | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> StateMessage:
        """Blocking convenience: one frame in, one ``state`` message out."""
        result = self.request(
            image,
            w=w,
            h=h,
            seq=seq,
            want=("state",),
            timeout=timeout,
            **kwargs,
        )
        return cast(StateMessage, result)

    def decide(
        self,
        image: bytes,
        *,
        w: int,
        h: int,
        seq: int | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> PlayMessage:
        """Blocking convenience: one frame in, one ``play`` message out."""
        result = self.request(
            image,
            w=w,
            h=h,
            seq=seq,
            want=("play",),
            timeout=timeout,
            **kwargs,
        )
        return cast(PlayMessage, result)

    def _wait_for(self, seq: int, types: set[str], timeout: float) -> ServerMessage:
        deadline = time.monotonic() + max(timeout, 0.0)
        with self._cv:
            while True:
                for index, message in enumerate(self._rx):
                    if message.get("seq") != seq:
                        continue
                    kind = message.get("type")
                    if kind == "error":
                        del self._rx[index]
                        error = message.get("error") or {}
                        raise ServerError(
                            str(error.get("code", "error")),
                            str(error.get("message", "")),
                        )
                    if kind in types:
                        del self._rx[index]
                        return cast(ServerMessage, message)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ClientTimeout(
                        f"timed out waiting for {sorted(types)} seq={seq}"
                    )
                self._cv.wait(remaining)

    # ---- worker ---------------------------------------------------------

    def _run(self) -> None:
        backoff = 0.5
        while not self._stop.is_set():
            connection = None
            try:
                connection = self._open()
                self._conn = connection
                self._send(
                    connection,
                    build_hello(
                        session_id=self.session_id,
                        client_name=self.client_name,
                        client_version=self.client_version,
                    ),
                )
                backoff = 0.5
                while not self._stop.is_set():
                    queued = self._pop_tx()
                    if queued is not None:
                        self._send(connection, queued)
                        continue
                    try:
                        raw = connection.recv(timeout=0.05)
                    except TimeoutError:
                        continue
                    self._handle(raw)
            except ClientError as exc:
                self._fatal = exc
                with self._cv:
                    self._cv.notify_all()
                break
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                if self._stop.is_set():
                    break
                if not self.reconnect:
                    break
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 10.0)
            finally:
                if connection is not None:
                    with contextlib.suppress(Exception):
                        connection.close()
                self._conn = None

    def _open(self) -> Any:
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise ClientError(
                "install 'clash-net-lib[client]' for the WebSocket binding"
            ) from exc
        return connect(
            self.url,
            max_size=1 << 20,
            open_timeout=self.connect_timeout,
        )

    def _send(self, connection: Any, message: Mapping[str, Any]) -> None:
        text = json.dumps(message, separators=(",", ":"), ensure_ascii=True)
        chunks = chunk_text(text, self.max_frame_bytes)
        if len(chunks) == 1:
            connection.send(text)
        else:
            connection.send(chunks)

    def _pop_tx(self) -> Mapping[str, Any] | None:
        with self._cv:
            return self._tx.popleft() if self._tx else None

    def _handle(self, raw: str | bytes) -> None:
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(message, dict):
            return
        if message.get("type") == "hello_ack":
            capabilities = message.get("capabilities")
            if isinstance(capabilities, dict):
                with self._cv:
                    self._capabilities = cast(Capabilities, capabilities)
                    self._cv.notify_all()
            return
        with self._cv:
            self._rx.append(message)
            self._cv.notify_all()
