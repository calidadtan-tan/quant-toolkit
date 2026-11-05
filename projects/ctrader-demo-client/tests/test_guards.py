import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ctrader_demo.config import load_dotenv, parse_dotenv
from ctrader_demo.constants import ALLOWED_OUTGOING_PAYLOAD_TYPES, PayloadType
from ctrader_demo.errors import DemoGuardError
from ctrader_demo.guards import (
    assert_account_id,
    assert_demo_host,
    assert_demo_port,
    guard_outgoing_envelope,
)
from tests.support import env


class GuardTests(unittest.TestCase):
    def test_demo_host_accepted(self):
        self.assertEqual(assert_demo_host("demo.ctraderapi.com"), "demo.ctraderapi.com")
        self.assertEqual(assert_demo_host(" DEMO.CTRADERAPI.COM. "), "demo.ctraderapi.com")

    def test_live_host_refused(self):
        for host in (
            "live.ctraderapi.com",
            "LIVE.CTRADERAPI.COM",
            "live1.p.ctrader.com",
            "live2.p.ctrader.com",
            "wss://live.ctraderapi.com",
        ):
            with self.subTest(host=host):
                with self.assertRaises(DemoGuardError) as caught:
                    assert_demo_host(host)
                self.assertIn("DEMO GUARD", str(caught.exception))
                self.assertIn("live", str(caught.exception).lower())

    def test_other_host_refused(self):
        with self.assertRaises(DemoGuardError):
            assert_demo_host("example.com")

    def test_protobuf_port_refused(self):
        with self.assertRaises(DemoGuardError) as caught:
            assert_demo_port(5035)
        self.assertIn("5036", str(caught.exception))

    def test_only_bound_account_accepted(self):
        self.assertEqual(assert_account_id(5360748), 5360748)
        self.assertEqual(assert_account_id("5360748"), 5360748)
        for bad in (5360749, 0, "1", True, 5360748.0, None, "live"):
            with self.subTest(bad=bad):
                with self.assertRaises(DemoGuardError) as caught:
                    assert_account_id(bad)
                self.assertIn("5360748", str(caught.exception))

    def test_outgoing_allow_list_blocks_orders(self):
        self.assertEqual(
            ALLOWED_OUTGOING_PAYLOAD_TYPES,
            frozenset(
                {
                    PayloadType.APPLICATION_AUTH_REQ,
                    PayloadType.ACCOUNT_AUTH_REQ,
                    PayloadType.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                    PayloadType.RECONCILE_REQ,
                    PayloadType.GET_POSITION_UNREALIZED_PNL_REQ,
                    PayloadType.AMEND_POSITION_SLTP_REQ,
                }
            ),
        )
        blocked = {
            PayloadType.NEW_ORDER_REQ: {},
            PayloadType.CANCEL_ORDER_REQ: {"ctidTraderAccountId": 5360748, "orderId": 1},
            PayloadType.AMEND_ORDER_REQ: {"ctidTraderAccountId": 5360748},
            PayloadType.CLOSE_POSITION_REQ: {"ctidTraderAccountId": 5360748, "positionId": 1},
        }
        for payload_type, payload in blocked.items():
            with self.subTest(payload_type=payload_type):
                with self.assertRaises(DemoGuardError):
                    guard_outgoing_envelope(
                        {"clientMsgId": "x", "payloadType": payload_type, "payload": payload}
                    )

    def test_amend_for_other_account_refused(self):
        with self.assertRaises(DemoGuardError):
            guard_outgoing_envelope(
                {
                    "clientMsgId": "x",
                    "payloadType": PayloadType.AMEND_POSITION_SLTP_REQ,
                    "payload": {"ctidTraderAccountId": 1, "positionId": 9, "stopLoss": 1.2},
                }
            )

    def test_env_live_host_exits_before_socket(self):
        with env(CTRADER_ACCOUNT_ID="5360748", CTRADER_HOST="live.ctraderapi.com"):
            from ctrader_demo.cli import main

            called = []

            def factory():
                called.append("connect")
                raise AssertionError("transport was constructed")

            code = main(["read-positions"], transport_factory=factory)
            self.assertEqual(code, 2)
            self.assertEqual(called, [])

    def test_env_wrong_account_exits_before_socket(self):
        with env(
            CTRADER_ACCOUNT_ID="999",
            CTRADER_CLIENT_ID="id",
            CTRADER_CLIENT_SECRET="sec",
            CTRADER_ACCESS_TOKEN="tok",
        ):
            from ctrader_demo.cli import main

            def factory():
                raise AssertionError("transport was constructed")

            code = main(["read-positions"], transport_factory=factory)
            self.assertEqual(code, 2)

    def test_package_source_does_not_dial_live(self):
        root = Path(__file__).resolve().parents[1] / "ctrader_demo"
        allowed = {"constants.py", "guards.py"}
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "live.ctraderapi.com" in text:
                self.assertIn(path.name, allowed, path)
        transport = (root / "transport.py").read_text(encoding="utf-8")
        self.assertIn('("demo.ctraderapi.com", 5036)', transport)
        self.assertNotIn("live.ctraderapi.com", transport)

    def test_connect_signature_has_no_host(self):
        from ctrader_demo.transport import SslWebSocketTransport

        parameters = inspect.signature(SslWebSocketTransport.connect).parameters
        self.assertNotIn("host", parameters)
        self.assertNotIn("port", parameters)

    def test_dotenv_does_not_override_real_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("CTRADER_ACCOUNT_ID=1\nCTRADER_CLIENT_ID=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"CTRADER_ACCOUNT_ID": "5360748"}, clear=False):
                os.environ.pop("CTRADER_CLIENT_ID", None)
                previous = os.getcwd()
                os.chdir(tmp)
                try:
                    load_dotenv()
                finally:
                    os.chdir(previous)
                self.assertEqual(os.environ["CTRADER_ACCOUNT_ID"], "5360748")
                self.assertEqual(os.environ["CTRADER_CLIENT_ID"], "from-file")

    def test_parse_dotenv_quotes_and_comments(self):
        parsed = parse_dotenv("# comment\nexport CLIENT_SECRET='abc'\nACCESS_TOKEN=\"tok\"\n\nNOPE\n")
        self.assertEqual(parsed["CLIENT_SECRET"], "abc")
        self.assertEqual(parsed["ACCESS_TOKEN"], "tok")
        self.assertNotIn("NOPE", parsed)


if __name__ == "__main__":
    unittest.main()
