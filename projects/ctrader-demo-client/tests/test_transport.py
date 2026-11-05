import unittest
from unittest.mock import patch

from ctrader_demo.transport import (
    SslWebSocketTransport,
    build_handshake,
    encode_frame,
    expected_accept,
    try_decode_frame,
    validate_handshake_response,
)


class FakeSocket:
    def __init__(self, incoming: bytes, chunk: int | None = None):
        self.incoming = bytearray(incoming)
        self.outgoing = bytearray()
        self.chunk = chunk

    def recv(self, size: int) -> bytes:
        if not self.incoming:
            return b""
        take = size if self.chunk is None else min(size, self.chunk)
        data = bytes(self.incoming[:take])
        del self.incoming[:take]
        return data

    def sendall(self, data: bytes) -> None:
        self.outgoing.extend(data)

    def settimeout(self, timeout: float) -> None:
        del timeout

    def close(self) -> None:
        return None


class TransportTests(unittest.TestCase):
    def test_rfc6455_accept_value(self):
        self.assertEqual(expected_accept("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

    def test_handshake_is_demo_json_port(self):
        raw = build_handshake("dGhlIHNhbXBsZSBub25jZQ==")
        text = raw.decode("ascii")
        self.assertIn("Host: demo.ctraderapi.com:5036", text)
        self.assertIn("Upgrade: websocket", text)
        self.assertNotIn("live.ctraderapi.com", text)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
            "\r\n{\"payloadType\":51}"
        ).encode("ascii")
        leftover = validate_handshake_response(response, "dGhlIHNhbXBsZSBub25jZQ==")
        self.assertEqual(leftover, b'{"payloadType":51}')

    def test_frame_roundtrip_including_extended_length(self):
        payload = b"x" * 200
        encoded = encode_frame(0x1, payload, mask=True, mask_key=b"\x01\x02\x03\x04")
        fin, opcode, decoded, rest = try_decode_frame(encoded)
        self.assertTrue(fin)
        self.assertEqual(opcode, 0x1)
        self.assertEqual(decoded, payload)
        self.assertEqual(rest, b"")
        self.assertIsNone(try_decode_frame(encoded[:5]))

    def test_recv_answers_ping_then_returns_text(self):
        ping = encode_frame(0x9, b"abc", mask=False)
        text = encode_frame(0x1, b'{"ok":true}', mask=False)
        sock = FakeSocket(ping + text, chunk=1)
        transport = SslWebSocketTransport()
        transport._sock = sock
        self.assertEqual(transport.recv_text(1), '{"ok":true}')
        self.assertEqual(sock.outgoing[0], 0x8A)
        self.assertTrue(sock.outgoing[1] & 0x80)

    def test_connect_dials_only_the_demo_literal(self):
        with patch(
            "ctrader_demo.transport.socket.create_connection",
            side_effect=RuntimeError("stop-before-network"),
        ) as create_connection:
            transport = SslWebSocketTransport()
            with self.assertRaises(RuntimeError):
                transport.connect()
            create_connection.assert_called_once()
            self.assertEqual(create_connection.call_args.args[0], ("demo.ctraderapi.com", 5036))
            self.assertIsNone(transport._sock)


if __name__ == "__main__":
    unittest.main()
