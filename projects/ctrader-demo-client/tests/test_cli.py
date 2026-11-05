import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ctrader_demo import amend_sltp, read_positions
from ctrader_demo.cli import main
from tests.support import FakeTransport, auth_responses, echo, env


def _run(argv, *, factory=None, urlopen=None, **environment):
    stdout = io.StringIO()
    stderr = io.StringIO()
    kwargs = {}
    if factory is not None:
        kwargs["transport_factory"] = factory
    if urlopen is not None:
        kwargs["urlopen"] = urlopen
    with env(**environment):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv, **kwargs)
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self._previous = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._previous)
        self._tmp.cleanup()

    def test_read_positions_prints_json_from_fake_proxy(self):
        transport = FakeTransport(
            auth_responses()
            + [
                echo(
                    2125,
                    {
                        "ctidTraderAccountId": 5360748,
                        "position": [
                            {
                                "positionId": 10,
                                "tradeData": {"symbolId": 4, "volume": 1000, "tradeSide": "BUY"},
                                "positionStatus": "POSITION_STATUS_OPEN",
                                "price": 1.2345,
                                "stopLoss": 1.2,
                                "takeProfit": 1.3,
                                "moneyDigits": 2,
                            }
                        ],
                    },
                ),
                echo(
                    2188,
                    {
                        "ctidTraderAccountId": 5360748,
                        "moneyDigits": 2,
                        "positionUnrealizedPnL": [
                            {"positionId": 10, "grossUnrealizedPnL": 250, "netUnrealizedPnL": 200}
                        ],
                    },
                ),
            ]
        )
        code, stdout, stderr = _run(
            ["read-positions"],
            factory=lambda: transport,
            CTRADER_ACCOUNT_ID="5360748",
            CTRADER_CLIENT_ID="test-client-id",
            CTRADER_CLIENT_SECRET="test-client-secret",
            CTRADER_ACCESS_TOKEN="test-access-token",
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["command"], "read-positions")
        self.assertEqual(payload["result"]["accountId"], 5360748)
        self.assertEqual(payload["result"]["host"], "demo.ctraderapi.com")
        self.assertEqual(payload["result"]["positions"][0]["netUnrealizedPnL"], "2")
        self.assertEqual(transport.payload_types(), [2100, 2149, 2102, 2124, 2187])
        self.assertNotIn("test-client-secret", stdout)

    def test_amend_without_prices_does_not_connect(self):
        def factory():
            raise AssertionError("transport was constructed")

        code, stdout, stderr = _run(
            ["amend-sl", "--position-id", "10"],
            factory=factory,
            CTRADER_ACCOUNT_ID="5360748",
            CTRADER_CLIENT_ID="id",
            CTRADER_CLIENT_SECRET="secret",
            CTRADER_ACCESS_TOKEN="token",
        )
        self.assertEqual(code, 1)
        self.assertEqual(stdout, stderr)
        report = json.loads(stdout)
        self.assertEqual(report["code"], 1)
        self.assertEqual(report["error"], "USAGE")
        self.assertFalse(report["ok"])
        self.assertIn("ProtoOAAmendPositionSLTPReq", report["message"])

    def test_auth_url_refuses_non_demo_host_before_printing(self):
        code, stdout, stderr = _run(
            ["auth-url", "--redirect-uri", "https://localhost/cb"],
            CTRADER_ACCOUNT_ID="5360748",
            CTRADER_CLIENT_ID="app-1",
            CTRADER_HOST="live.ctraderapi.com",
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, stderr)
        report = json.loads(stdout)
        self.assertEqual(report["code"], 2)
        self.assertEqual(report["error"], "DEMO_GUARD")
        self.assertIn("message", report)
        self.assertIn("DEMO GUARD", report["message"])
        self.assertNotIn("id.ctrader.com", stdout)
        self.assertNotIn("result", report)

    def test_example_env_has_empty_secrets_and_demo_binding(self):
        example = Path(__file__).resolve().parents[1] / ".env.example"
        text = example.read_text(encoding="utf-8")
        self.assertIn("CTRADER_HOST=demo.ctraderapi.com", text)
        self.assertIn("CTRADER_ACCOUNT_ID=5360748", text)
        self.assertIn("CTRADER_CLIENT_ID=\n", text)
        self.assertIn("CTRADER_CLIENT_SECRET=\n", text)
        self.assertIn("CTRADER_ACCESS_TOKEN=\n", text)
        self.assertIn("CTRADER_REFRESH_TOKEN=\n", text)
        self.assertIn("CTRADER_REDIRECT_URI=https://localhost", text)
        self.assertNotIn("live.ctraderapi.com", text)
        gitignore = (example.parent / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env\n", gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_module_entrypoints_return_the_same_report(self):
        transport = FakeTransport(
            auth_responses()
            + [
                echo(2125, {"ctidTraderAccountId": 5360748, "position": []}),
                echo(2188, {"ctidTraderAccountId": 5360748, "moneyDigits": 2, "positionUnrealizedPnL": []}),
            ]
        )
        with env(
            CTRADER_ACCOUNT_ID="5360748",
            CTRADER_CLIENT_ID="test-client-id",
            CTRADER_CLIENT_SECRET="test-client-secret",
            CTRADER_ACCESS_TOKEN="test-access-token",
        ):
            report = read_positions(transport_factory=lambda: transport)
        self.assertEqual(report["code"], 0)
        self.assertEqual(report["message"], "ok")
        self.assertEqual(report["result"]["positionCount"], 0)
        self.assertEqual(transport.payload_types(), [2100, 2149, 2102, 2124, 2187])

        def factory():
            raise AssertionError("transport was constructed")

        with env(CTRADER_ACCOUNT_ID="1", CTRADER_HOST="demo.ctraderapi.com"):
            denied = amend_sltp(10, stop_loss=1.1, transport_factory=factory)
        self.assertEqual(denied["code"], 2)
        self.assertEqual(denied["error"], "DEMO_GUARD")
        self.assertIn("5360748", denied["message"])


if __name__ == "__main__":
    unittest.main()
