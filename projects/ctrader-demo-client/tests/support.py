"""Shared fixtures. These tests never open a socket."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from ctrader_demo.config import TradingConfig
from ctrader_demo.errors import ApiError

ENV_KEYS = (
    "CTRADER_CLIENT_ID",
    "CTRADER_CLIENT_SECRET",
    "CTRADER_ACCESS_TOKEN",
    "CTRADER_REFRESH_TOKEN",
    "CTRADER_ACCOUNT_ID",
    "CTRADER_HOST",
    "CTRADER_REDIRECT_URI",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
    "ACCOUNT_ID",
    "REDIRECT_URI",
)


def env(**overrides: str):
    base = {key: "" for key in ENV_KEYS}
    base.update(overrides)
    return patch.dict(os.environ, base, clear=False)


def trading_config(**overrides) -> TradingConfig:
    values = {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "access_token": "test-access-token",
        "account_id": 5360748,
        "host": "demo.ctraderapi.com",
        "port": 5036,
        "refresh_token": "test-refresh-token",
    }
    values.update(overrides)
    return TradingConfig(**values)


class FakeTransport:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.sent: list[dict] = []
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def send_text(self, text: str) -> None:
        if not self.connected:
            raise AssertionError("send_text before connect")
        self.sent.append(json.loads(text))

    def recv_text(self, timeout: float) -> str:
        del timeout
        if not self._responses:
            raise ApiError("TIMEOUT", "no scripted response", 0)
        item = json.loads(json.dumps(self._responses.pop(0)))
        if item.get("clientMsgId") == "<echo>":
            item["clientMsgId"] = self.sent[-1]["clientMsgId"]
        return json.dumps(item)

    def close(self) -> None:
        self.closed = True

    def payload_types(self) -> list[int]:
        return [int(message["payloadType"]) for message in self.sent]


def echo(payload_type: int, payload: dict) -> dict:
    return {"clientMsgId": "<echo>", "payloadType": payload_type, "payload": payload}


# Observed Open API id for DEMO login 5360748. Tests must not treat these as the same number.
DEMO_CTID = 49216463


def _fixture_login(account: dict) -> int | None:
    for key in ("traderLogin", "login", "trader_login", "accountLogin"):
        if key in account and account[key] is not None:
            try:
                return int(account[key])
            except (TypeError, ValueError):
                return None
    return None


def auth_responses(*, accounts: list[dict] | None = None, scope=1) -> list[dict]:
    if accounts is None:
        accounts = [{"ctidTraderAccountId": DEMO_CTID, "isLive": False, "traderLogin": 5360748}]
    auth_ctid = DEMO_CTID
    for account in accounts:
        if _fixture_login(account) == 5360748 and account.get("ctidTraderAccountId") is not None:
            auth_ctid = int(account["ctidTraderAccountId"])
            break
    return [
        echo(2101, {}),
        echo(2150, {"accessToken": "test-access-token", "permissionScope": scope, "ctidTraderAccount": accounts}),
        echo(2103, {"ctidTraderAccountId": auth_ctid}),
    ]
