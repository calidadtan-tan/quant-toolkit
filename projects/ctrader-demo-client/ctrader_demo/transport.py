"""Minimal TLS WebSocket client for the demo JSON proxy.

The socket address is the literal ``demo.ctraderapi.com:5036``. There is no
host argument, so a caller cannot point this transport at a live proxy.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct

from ctrader_demo.constants import (
    ALLOWED_HOST,
    ALLOWED_JSON_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_FRAME_BYTES,
    WS_GUID,
)
from ctrader_demo.errors import ApiError, DemoGuardError


def _assert_socket_constants() -> None:
    if ALLOWED_HOST != "demo.ctraderapi.com" or ALLOWED_JSON_PORT != 5036:
        raise DemoGuardError(
            "DEMO GUARD: demo endpoint constants were changed. Refusing to open a socket."
        )


def build_handshake(key_b64: str) -> bytes:
    if not key_b64 or any(char in key_b64 for char in "\r\n"):
        raise ValueError("invalid websocket key")
    lines = [
        "GET / HTTP/1.1",
        "Host: demo.ctraderapi.com:5036",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key_b64}",
        "Sec-WebSocket-Version: 13",
        "",
        "",
    ]
    return "\r\n".join(lines).encode("ascii")


def expected_accept(key_b64: str) -> str:
    digest = hashlib.sha1((key_b64 + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def validate_handshake_response(raw: bytes, key_b64: str) -> bytes:
    """Return bytes that arrived after the HTTP headers."""

    separator = raw.find(b"\r\n\r\n")
    if separator < 0:
        raise ApiError("HANDSHAKE", "WebSocket handshake response was incomplete.", 0)
    head = raw[:separator].decode("iso-8859-1", errors="replace")
    status_line = head.split("\r\n", 1)[0]
    parts = status_line.split()
    if len(parts) < 2 or parts[1] != "101":
        raise ApiError("HANDSHAKE", f"WebSocket handshake failed: {status_line}", 0)
    headers: dict[str, str] = {}
    for line in head.split("\r\n")[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    accept = headers.get("sec-websocket-accept", "")
    if accept != expected_accept(key_b64):
        raise ApiError("HANDSHAKE", "WebSocket accept header did not match.", 0)
    return raw[separator + 4 :]


def encode_frame(opcode: int, payload: bytes, *, mask: bool, mask_key: bytes | None = None) -> bytes:
    original_length = len(payload)
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    mask_bit = 0x80 if mask else 0x00
    if original_length < 126:
        header.append(mask_bit | original_length)
    elif original_length < 65536:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", original_length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", original_length))
    body = payload
    if mask:
        key = mask_key if mask_key is not None else os.urandom(4)
        if len(key) != 4:
            raise ValueError("websocket mask must be 4 bytes")
        header.extend(key)
        body = bytes(byte ^ key[index % 4] for index, byte in enumerate(payload))
    header.extend(body)
    return bytes(header)


def try_decode_frame(buf: bytes) -> tuple[bool, int, bytes, bytes] | None:
    """Decode one frame. Return ``(fin, opcode, payload, rest)`` or ``None``."""

    if len(buf) < 2:
        return None
    first, second = buf[0], buf[1]
    fin = (first & 0x80) != 0
    opcode = first & 0x0F
    masked = (second & 0x80) != 0
    length = second & 0x7F
    offset = 2
    if length == 126:
        if len(buf) < offset + 2:
            return None
        length = struct.unpack("!H", buf[offset : offset + 2])[0]
        offset += 2
    elif length == 127:
        if len(buf) < offset + 8:
            return None
        length = struct.unpack("!Q", buf[offset : offset + 8])[0]
        offset += 8
    if length > MAX_FRAME_BYTES:
        raise ApiError("FRAME", "Refusing an oversized WebSocket frame.", 0)
    mask_key = b""
    if masked:
        if len(buf) < offset + 4:
            return None
        mask_key = buf[offset : offset + 4]
        offset += 4
    if len(buf) < offset + length:
        return None
    payload = buf[offset : offset + length]
    if masked:
        payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
    rest = buf[offset + length :]
    return fin, opcode, payload, rest


class SslWebSocketTransport:
    """Text WebSocket over TLS to the demo JSON port."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buffer = b""

    def connect(self) -> None:
        _assert_socket_constants()
        raw: socket.socket | None = None
        try:
            raw = socket.create_connection(("demo.ctraderapi.com", 5036), timeout=self.timeout)
            raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            context = ssl.create_default_context()
            self._sock = context.wrap_socket(raw, server_hostname="demo.ctraderapi.com")
            raw = None
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            self._sock.sendall(build_handshake(key))
            raw_response = self._read_until_headers()
            self._buffer = validate_handshake_response(raw_response, key)
        except Exception:
            if raw is not None:
                raw.close()
            self.close()
            raise

    def send_text(self, text: str) -> None:
        sock = self._require_socket()
        frame = encode_frame(0x1, text.encode("utf-8"), mask=True)
        sock.sendall(frame)

    def recv_text(self, timeout: float) -> str:
        sock = self._require_socket()
        sock.settimeout(timeout)
        fragments: list[bytes] = []
        while True:
            fin, opcode, payload = self._read_frame()
            if opcode == 0x9:  # ping
                sock.sendall(encode_frame(0xA, payload, mask=True))
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode == 0x8:
                raise ApiError("CLOSED", "Demo WebSocket closed by the proxy.", 0)
            if opcode == 0x1:
                if fin:
                    return payload.decode("utf-8")
                fragments = [payload]
                continue
            if opcode == 0x0:
                fragments.append(payload)
                if fin:
                    return b"".join(fragments).decode("utf-8")
                continue
            raise ApiError("FRAME", f"Unsupported WebSocket opcode {opcode}.", 0)

    def close(self) -> None:
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _require_socket(self) -> socket.socket:
        if self._sock is None:
            raise ApiError("NOT_CONNECTED", "Demo WebSocket is not connected.", 0)
        return self._sock

    def _read_until_headers(self) -> bytes:
        sock = self._require_socket()
        data = b""
        while b"\r\n\r\n" not in data:
            if len(data) > 8192:
                raise ApiError("HANDSHAKE", "WebSocket handshake headers were too large.", 0)
            chunk = sock.recv(4096)
            if not chunk:
                raise ApiError("HANDSHAKE", "Connection closed during WebSocket handshake.", 0)
            data += chunk
        return data

    def _read_frame(self) -> tuple[bool, int, bytes]:
        sock = self._require_socket()
        while True:
            decoded = try_decode_frame(self._buffer)
            if decoded is not None:
                fin, opcode, payload, rest = decoded
                self._buffer = rest
                return fin, opcode, payload
            if len(self._buffer) > MAX_FRAME_BYTES:
                raise ApiError("FRAME", "Refusing an oversized WebSocket buffer.", 0)
            chunk = sock.recv(4096)
            if not chunk:
                raise ApiError("CLOSED", "Demo WebSocket closed by the proxy.", 0)
            self._buffer += chunk
