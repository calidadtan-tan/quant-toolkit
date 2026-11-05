import inspect
import unittest

from ctrader_demo.constants import PayloadType

CTID = 49216463
from ctrader_demo.errors import ApiError, DemoGuardError
from ctrader_demo.messages import (
    build_account_auth_req,
    build_amend_position_sltp_req,
    build_close_position_req,
    build_market_order_req,
    build_application_auth_req,
    build_reconcile_req,
    build_unrealized_pnl_req,
    normalize_open_positions,
    parse_amend_execution,
)


class MessageShapeTests(unittest.TestCase):
    def test_application_auth_shape(self):
        message = build_application_auth_req("client-id", "client-secret", "cm_id_2")
        self.assertEqual(
            message,
            {
                "clientMsgId": "cm_id_2",
                "payloadType": 2100,
                "payload": {"clientId": "client-id", "clientSecret": "client-secret"},
            },
        )

    def test_account_auth_is_bound_to_demo_account(self):
        message = build_account_auth_req("access-token", CTID, "auth-1")
        self.assertEqual(message["payloadType"], PayloadType.ACCOUNT_AUTH_REQ)
        self.assertEqual(
            message["payload"],
            {"ctidTraderAccountId": CTID, "accessToken": "access-token"},
        )
        self.assertNotIn("account_id", inspect.signature(build_account_auth_req).parameters)

    def test_reconcile_and_pnl_shapes(self):
        reconcile = build_reconcile_req(CTID, "rec-1")
        self.assertEqual(
            reconcile,
            {
                "clientMsgId": "rec-1",
                "payloadType": 2124,
                "payload": {"ctidTraderAccountId": CTID, "returnProtectionOrders": False},
            },
        )
        pnl = build_unrealized_pnl_req(CTID, "pnl-1")
        self.assertEqual(
            pnl,
            {
                "clientMsgId": "pnl-1",
                "payloadType": 2187,
                "payload": {"ctidTraderAccountId": CTID},
            },
        )

    def test_amend_sltp_shape_matches_proto_fields(self):
        message = build_amend_position_sltp_req(
            ctid_trader_account_id=CTID,
            position_id=99,
            stop_loss=1.23456,
            take_profit=1.26543,
            client_msg_id="amend-1",
        )
        self.assertEqual(
            message,
            {
                "clientMsgId": "amend-1",
                "payloadType": 2110,
                "payload": {
                    "ctidTraderAccountId": CTID,
                    "positionId": 99,
                    "stopLoss": 1.23456,
                    "takeProfit": 1.26543,
                },
            },
        )
        self.assertNotIn("guaranteedStopLoss", message["payload"])
        self.assertNotIn("account_id", inspect.signature(build_amend_position_sltp_req).parameters)

    def test_market_order_and_close_shapes(self):
        order = build_market_order_req(
            ctid_trader_account_id=CTID,
            symbol_id=7,
            side="buy",
            volume=1000,
            stop_loss=1.08,
            take_profit=1.12,
            label="demo",
            client_msg_id="mkt-1",
        )
        self.assertEqual(
            order,
            {
                "clientMsgId": "mkt-1",
                "payloadType": 2106,
                "payload": {
                    "ctidTraderAccountId": CTID,
                    "symbolId": 7,
                    "orderType": 1,
                    "tradeSide": 1,
                    "volume": 1000,
                    "stopLoss": 1.08,
                    "takeProfit": 1.12,
                    "label": "demo",
                },
            },
        )
        self.assertNotIn("limitPrice", order["payload"])
        self.assertNotIn("stopPrice", order["payload"])
        close = build_close_position_req(
            ctid_trader_account_id=CTID,
            position_id=10,
            volume=1000,
            client_msg_id="cls-1",
        )
        self.assertEqual(
            close,
            {
                "clientMsgId": "cls-1",
                "payloadType": 2111,
                "payload": {"ctidTraderAccountId": CTID, "positionId": 10, "volume": 1000},
            },
        )
        with self.assertRaises(ValueError):
            build_market_order_req(ctid_trader_account_id=CTID, symbol_id=7, side="LIMIT", volume=1000)
        with self.assertRaises(ValueError):
            build_market_order_req(ctid_trader_account_id=CTID, symbol_id=7, side="BUY", volume=0)

    def test_amend_can_send_only_one_price(self):
        only_sl = build_amend_position_sltp_req(
            ctid_trader_account_id=CTID, position_id=3, stop_loss=1.5, client_msg_id="s"
        )
        self.assertEqual(set(only_sl["payload"]), {"ctidTraderAccountId", "positionId", "stopLoss"})
        with self.assertRaises(ValueError):
            build_amend_position_sltp_req(ctid_trader_account_id=CTID, position_id=3)
        with self.assertRaises(ValueError):
            build_amend_position_sltp_req(ctid_trader_account_id=CTID, position_id=0, stop_loss=1.2)
        with self.assertRaises(ValueError):
            build_amend_position_sltp_req(ctid_trader_account_id=CTID, position_id=3, stop_loss=0)
        with self.assertRaises(ValueError):
            build_amend_position_sltp_req(ctid_trader_account_id=CTID, position_id=3, take_profit=float("nan"))

    def test_normalize_scales_money_and_drops_closed_positions(self):
        reconcile = {
            "payloadType": 2125,
            "payload": {
                "ctidTraderAccountId": CTID,
                "position": [
                    {
                        "positionId": 10,
                        "tradeData": {
                            "symbolId": 1,
                            "volume": 100000,
                            "tradeSide": 1,
                            "label": "demo",
                        },
                        "positionStatus": 1,
                        "swap": -150000000,
                        "price": 1.1,
                        "stopLoss": 1.08,
                        "takeProfit": 1.12,
                        "commission": 20000000,
                        "usedMargin": 5000000000,
                        "moneyDigits": 8,
                    },
                    {
                        "positionId": 11,
                        "tradeData": {"symbolId": 2, "volume": 200, "tradeSide": "SELL"},
                        "positionStatus": 2,
                        "price": 150.0,
                        "moneyDigits": 2,
                    },
                    {
                        "positionId": 12,
                        "tradeData": {"symbolId": 3, "volume": 100, "tradeSide": 2},
                        "positionStatus": "POSITION_STATUS_CREATED",
                        "price": 1.0,
                        "moneyDigits": 2,
                    },
                ],
                "order": [{"orderId": 7}],
            },
        }
        pnl = {
            "payloadType": 2188,
            "payload": {
                "ctidTraderAccountId": str(CTID),
                "moneyDigits": 8,
                "positionUnrealizedPnL": [
                    {
                        "positionId": 10,
                        "grossUnrealizedPnL": 123456789,
                        "netUnrealizedPnL": -50000000,
                    }
                ],
            },
        }
        result = normalize_open_positions(reconcile, pnl, expected_ctid=CTID)
        self.assertEqual(result["accountId"], 5360748)
        self.assertEqual(result["traderLogin"], 5360748)
        self.assertEqual(result["ctidTraderAccountId"], CTID)
        self.assertEqual(result["host"], "demo.ctraderapi.com")
        self.assertEqual(result["endpoint"], "wss://demo.ctraderapi.com:5036")
        self.assertEqual(result["positionCount"], 1)
        self.assertEqual(
            result["positions"][0],
            {
                "positionId": 10,
                "symbolId": 1,
                "tradeSide": "BUY",
                "positionStatus": "POSITION_STATUS_OPEN",
                "volume": 100000,
                "volumeUnits": "1000.00",
                "entryPrice": 1.1,
                "stopLoss": 1.08,
                "takeProfit": 1.12,
                "swap": "-1.5",
                "commission": "0.2",
                "usedMargin": "50",
                "moneyDigits": 8,
                "grossUnrealizedPnL": "1.23456789",
                "netUnrealizedPnL": "-0.5",
                "pnlMoneyDigits": 8,
                "label": "demo",
            },
        )

    def test_missing_pnl_money_digits_is_not_guessed(self):
        with self.assertRaises(ApiError) as caught:
            normalize_open_positions(
                {"payload": {"ctidTraderAccountId": CTID, "position": []}},
                {"payload": {"ctidTraderAccountId": CTID, "positionUnrealizedPnL": []}},
                expected_ctid=CTID,
            )
        self.assertEqual(caught.exception.error_code, "MISSING_MONEY_DIGITS")

    def test_foreign_reconcile_account_refused(self):
        with self.assertRaises(DemoGuardError):
            normalize_open_positions(
                {"payload": {"ctidTraderAccountId": 1, "position": []}},
                {"payload": {"ctidTraderAccountId": CTID, "moneyDigits": 2, "positionUnrealizedPnL": []}},
                expected_ctid=CTID,
            )

    def test_rejected_execution_is_an_error(self):
        with self.assertRaises(ApiError) as caught:
            parse_amend_execution(
                {
                    "payloadType": 2126,
                    "payload": {
                        "ctidTraderAccountId": CTID,
                        "executionType": 7,
                        "errorCode": "TRADING_BAD_STOPS",
                        "position": {"positionId": 99},
                    },
                },
                requested_position_id=99,
                expected_ctid=CTID,
            )
        self.assertEqual(caught.exception.error_code, "TRADING_BAD_STOPS")

    def test_accepted_execution_reports_prices(self):
        result = parse_amend_execution(
            {
                "payload": {
                    "ctidTraderAccountId": CTID,
                    "executionType": "ORDER_ACCEPTED",
                    "position": {"positionId": 99, "stopLoss": 1.23456, "takeProfit": 1.26543},
                }
            },
            requested_position_id=99,
            expected_ctid=CTID,
        )
        self.assertEqual(result["traderLogin"], 5360748)
        self.assertEqual(result["ctidTraderAccountId"], CTID)
        self.assertEqual(result["executionType"], "ORDER_ACCEPTED")
        self.assertEqual(result["stopLoss"], 1.23456)
        self.assertEqual(result["takeProfit"], 1.26543)
        self.assertIsNone(result["errorCode"])


if __name__ == "__main__":
    unittest.main()
