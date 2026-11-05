import unittest

from ctrader_demo.constants import PayloadType
from ctrader_demo.errors import ApiError, DemoGuardError
from ctrader_demo.session import DemoClient
from tests.support import FakeTransport, auth_responses, echo, trading_config


def _open_position_responses():
    return auth_responses() + [
        echo(
            2125,
            {
                "ctidTraderAccountId": 5360748,
                "position": [
                    {
                        "positionId": 10,
                        "tradeData": {"symbolId": 1, "volume": 1000, "tradeSide": 1},
                        "positionStatus": 1,
                        "price": 1.1,
                        "stopLoss": 1.0,
                        "takeProfit": 1.2,
                        "swap": 0,
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
                    {"positionId": 10, "grossUnrealizedPnL": 150, "netUnrealizedPnL": 125}
                ],
            },
        ),
    ]


class SessionTests(unittest.TestCase):
    def test_read_sequence_and_scaled_pnl(self):
        transport = FakeTransport([{"payloadType": 51, "payload": {}}, *_open_position_responses()])
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        result = client.read_positions()
        self.assertEqual(
            transport.payload_types(),
            [2100, 2149, 2102, 2124, 2187],
        )
        self.assertEqual(result["positions"][0]["grossUnrealizedPnL"], "1.5")
        self.assertEqual(result["positions"][0]["netUnrealizedPnL"], "1.25")
        self.assertEqual(result["positions"][0]["volumeUnits"], "10.00")
        sent_accounts = [
            message["payload"].get("ctidTraderAccountId")
            for message in transport.sent
            if "ctidTraderAccountId" in message["payload"]
        ]
        self.assertEqual(sent_accounts, [5360748, 5360748, 5360748])
        client.close()
        self.assertTrue(transport.closed)

    def test_live_flag_stops_before_account_auth(self):
        transport = FakeTransport(
            auth_responses(accounts=[{"ctidTraderAccountId": 5360748, "isLive": True}])[:2]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        with self.assertRaises(DemoGuardError) as caught:
            client.authorize()
        self.assertIn("isLive", str(caught.exception))
        self.assertEqual(transport.payload_types(), [2100, 2149])
        self.assertNotIn(PayloadType.ACCOUNT_AUTH_REQ, transport.payload_types())
        self.assertNotIn(PayloadType.RECONCILE_REQ, transport.payload_types())
        self.assertNotIn(PayloadType.AMEND_POSITION_SLTP_REQ, transport.payload_types())

    def test_other_granted_account_is_not_authorized(self):
        transport = FakeTransport(
            auth_responses(
                accounts=[
                    {"ctidTraderAccountId": 999001, "isLive": False},
                    {"ctidTraderAccountId": 999002, "isLive": True},
                ]
            )[:2]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        with self.assertRaises(DemoGuardError):
            client.authorize()
        self.assertEqual(transport.payload_types(), [2100, 2149])

    def test_live_neighbor_does_not_change_target_account(self):
        transport = FakeTransport(
            auth_responses(
                accounts=[
                    {"ctidTraderAccountId": 999002, "isLive": True},
                    {"ctidTraderAccountId": 5360748, "isLive": False},
                ]
            )
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        account_auth = transport.sent[2]
        self.assertEqual(account_auth["payloadType"], 2102)
        self.assertEqual(account_auth["payload"]["ctidTraderAccountId"], 5360748)

    def test_reconcile_account_mismatch_does_not_request_pnl(self):
        transport = FakeTransport(
            auth_responses()
            + [echo(2125, {"ctidTraderAccountId": 42, "position": []})]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        with self.assertRaises(DemoGuardError):
            client.read_positions()
        self.assertNotIn(2187, transport.payload_types())

    def test_view_scope_blocks_amend_before_send(self):
        transport = FakeTransport(auth_responses(scope="SCOPE_VIEW"))
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        with self.assertRaises(DemoGuardError) as caught:
            client.amend_sltp(position_id=10, stop_loss=1.05, take_profit=None)
        self.assertIn("ProtoOAAmendPositionSLTPReq", str(caught.exception))
        self.assertNotIn(2110, transport.payload_types())

    def test_amend_sends_2110_after_auth(self):
        transport = FakeTransport(
            auth_responses(scope=1)
            + [
                echo(
                    2126,
                    {
                        "ctidTraderAccountId": 5360748,
                        "executionType": 2,
                        "position": {"positionId": 10, "stopLoss": 1.05, "takeProfit": 1.25},
                    },
                )
            ]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        result = client.amend_sltp(position_id=10, stop_loss=1.05, take_profit=1.25)
        amend = transport.sent[-1]
        self.assertEqual(amend["payloadType"], 2110)
        self.assertEqual(
            amend["payload"],
            {
                "ctidTraderAccountId": 5360748,
                "positionId": 10,
                "stopLoss": 1.05,
                "takeProfit": 1.25,
            },
        )
        self.assertEqual(result["executionType"], "ORDER_ACCEPTED")
        self.assertEqual(result["positionId"], 10)

    def test_send_refuses_new_order_before_write(self):
        transport = FakeTransport([])
        client = DemoClient(trading_config(), transport)
        with self.assertRaises(DemoGuardError):
            client.send(
                {
                    "clientMsgId": "x",
                    "payloadType": PayloadType.NEW_ORDER_REQ,
                    "payload": {"ctidTraderAccountId": 5360748, "symbolId": 1},
                }
            )
        self.assertEqual(transport.sent, [])
        self.assertFalse(transport.connected)

    def test_error_description_redacts_secrets(self):
        transport = FakeTransport(
            [
                echo(
                    2142,
                    {
                        "errorCode": "CH_CLIENT_AUTH_FAILURE",
                        "description": "bad secret test-client-secret and token test-access-token",
                    },
                )
            ]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        with self.assertRaises(ApiError) as caught:
            client.authorize()
        text = str(caught.exception)
        self.assertNotIn("test-client-secret", text)
        self.assertNotIn("test-access-token", text)
        self.assertIn("***", text)

    def test_foreign_config_account_cannot_construct_client(self):
        with self.assertRaises(DemoGuardError):
            DemoClient(trading_config(account_id=1), FakeTransport([]))


if __name__ == "__main__":
    unittest.main()
