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
                "ctidTraderAccountId": 49216463,
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
                "ctidTraderAccountId": 49216463,
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
        self.assertEqual(sent_accounts, [49216463, 49216463, 49216463])
        self.assertEqual(result["traderLogin"], 5360748)
        self.assertEqual(result["ctidTraderAccountId"], 49216463)
        client.close()
        self.assertTrue(transport.closed)

    def test_login_5360748_resolves_to_different_ctid(self):
        """5360748 is traderLogin. The API id is a different ctidTraderAccountId.

        An entry whose ctid equals the login but whose traderLogin does not
        must not be authorized.
        """

        transport = FakeTransport(
            auth_responses(
                accounts=[
                    {"ctidTraderAccountId": 5360748, "traderLogin": 999001, "isLive": False},
                    {"ctidTraderAccountId": 49216463, "traderLogin": 5360748, "isLive": False},
                ]
            )
            + [
                echo(2125, {"ctidTraderAccountId": 49216463, "position": []}),
                echo(
                    2188,
                    {"ctidTraderAccountId": 49216463, "moneyDigits": 2, "positionUnrealizedPnL": []},
                ),
            ]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        result = client.read_positions()
        account_auth = transport.sent[2]
        self.assertEqual(account_auth["payloadType"], 2102)
        self.assertEqual(account_auth["payload"]["ctidTraderAccountId"], 49216463)
        sent_ctids = [
            message["payload"].get("ctidTraderAccountId")
            for message in transport.sent
            if "ctidTraderAccountId" in message["payload"]
        ]
        self.assertEqual(sent_ctids, [49216463, 49216463, 49216463])
        self.assertNotIn(5360748, sent_ctids)
        self.assertEqual(result["traderLogin"], 5360748)
        self.assertEqual(result["ctidTraderAccountId"], 49216463)

    def test_live_flag_stops_before_account_auth(self):
        transport = FakeTransport(
            auth_responses(
                accounts=[{"ctidTraderAccountId": 49216463, "traderLogin": 5360748, "isLive": True}]
            )[:2]
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
                    {"ctidTraderAccountId": 999001, "traderLogin": 111, "isLive": False},
                    {"ctidTraderAccountId": 5360748, "traderLogin": 222, "isLive": True},
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
                    {"ctidTraderAccountId": 999002, "traderLogin": 111, "isLive": True},
                    {"ctidTraderAccountId": 49216463, "login": 5360748, "isLive": False},
                ]
            )
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        account_auth = transport.sent[2]
        self.assertEqual(account_auth["payloadType"], 2102)
        self.assertEqual(account_auth["payload"]["ctidTraderAccountId"], 49216463)

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
                        "ctidTraderAccountId": 49216463,
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
                "ctidTraderAccountId": 49216463,
                "positionId": 10,
                "stopLoss": 1.05,
                "takeProfit": 1.25,
            },
        )
        self.assertEqual(result["executionType"], "ORDER_ACCEPTED")
        self.assertEqual(result["positionId"], 10)

    def test_open_market_sends_only_market_on_resolved_ctid(self):
        transport = FakeTransport(
            auth_responses()
            + [
                echo(
                    2126,
                    {
                        "ctidTraderAccountId": 49216463,
                        "executionType": 3,
                        "position": {
                            "positionId": 77,
                            "stopLoss": 1.08,
                            "takeProfit": 1.12,
                            "tradeData": {"symbolId": 7, "volume": 1000, "tradeSide": 1},
                        },
                        "order": {
                            "orderId": 88,
                            "tradeData": {"symbolId": 7, "volume": 1000, "tradeSide": 1},
                        },
                    },
                )
            ]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        result = client.open_market(
            symbol_id=7,
            side="SELL",
            volume=1000,
            stop_loss=1.08,
            take_profit=1.12,
            label="demo",
        )
        order = transport.sent[-1]
        self.assertEqual(order["payloadType"], 2106)
        self.assertEqual(
            order["payload"],
            {
                "ctidTraderAccountId": 49216463,
                "symbolId": 7,
                "orderType": 1,
                "tradeSide": 2,
                "volume": 1000,
                "stopLoss": 1.08,
                "takeProfit": 1.12,
                "label": "demo",
            },
        )
        self.assertEqual(result["positionId"], 77)
        self.assertEqual(result["orderId"], 88)
        self.assertEqual(result["executionType"], "ORDER_FILLED")
        self.assertNotIn(2108, transport.payload_types())
        self.assertNotIn(2109, transport.payload_types())

    def test_close_position_defaults_to_full_open_volume(self):
        transport = FakeTransport(
            auth_responses()
            + [
                echo(
                    2125,
                    {
                        "ctidTraderAccountId": 49216463,
                        "position": [
                            {
                                "positionId": 10,
                                "positionStatus": 1,
                                "tradeData": {"symbolId": 1, "volume": 1000, "tradeSide": 1},
                            }
                        ],
                    },
                ),
                echo(
                    2126,
                    {
                        "ctidTraderAccountId": 49216463,
                        "executionType": 3,
                        "position": {"positionId": 10, "tradeData": {"symbolId": 1, "volume": 1000, "tradeSide": 1}},
                    },
                ),
            ]
        )
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        result = client.close_position(position_id=10)
        close = transport.sent[-1]
        self.assertEqual(close["payloadType"], 2111)
        self.assertEqual(
            close["payload"],
            {"ctidTraderAccountId": 49216463, "positionId": 10, "volume": 1000},
        )
        self.assertEqual(result["positionId"], 10)
        self.assertEqual(transport.payload_types()[-2:], [2124, 2111])

    def test_close_position_partial_volume_and_refuses_oversize(self):
        def scripted():
            return FakeTransport(
                auth_responses()
                + [
                    echo(
                        2125,
                        {
                            "ctidTraderAccountId": 49216463,
                            "position": [
                                {
                                    "positionId": 10,
                                    "positionStatus": "POSITION_STATUS_OPEN",
                                    "tradeData": {"volume": 1000},
                                }
                            ],
                        },
                    ),
                    echo(
                        2126,
                        {
                            "ctidTraderAccountId": 49216463,
                            "executionType": 2,
                            "position": {"positionId": 10},
                        },
                    ),
                ]
            )

        transport = scripted()
        client = DemoClient(trading_config(), transport)
        client.connect()
        client.authorize()
        client.close_position(position_id=10, volume=400)
        self.assertEqual(transport.sent[-1]["payload"]["volume"], 400)

        oversized = scripted()
        other = DemoClient(trading_config(), oversized)
        other.connect()
        other.authorize()
        with self.assertRaises(ValueError):
            other.close_position(position_id=10, volume=1001)
        self.assertNotIn(2111, oversized.payload_types())

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
