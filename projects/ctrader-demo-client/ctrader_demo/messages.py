"""JSON bodies for the Open API messages this DEMO client sends and reads.

Field names follow the official JSON mapping (camelCase proto names). Monetary
integers that are scaled by ``moneyDigits`` are converted with ``Decimal``.
Position volume is in 0.01 units (1000 in the protocol means 10.00 units).
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal
from typing import Any

from ctrader_demo.constants import (
    ALLOWED_HOST,
    ALLOWED_TRADER_LOGIN,
    DEMO_WEBSOCKET_URL,
    EXECUTION_TYPE_NAMES,
    OPEN_POSITION_STATUSES,
    POSITION_STATUS_NAMES,
    REJECTED_EXECUTION_TYPES,
    TRADE_SIDE_NAMES,
    PayloadType,
)
from ctrader_demo.errors import ApiError
from ctrader_demo.guards import assert_resolved_ctid

JsonObject = dict[str, Any]


def new_client_msg_id() -> str:
    return str(uuid.uuid4())


def envelope(payload_type: int, payload: JsonObject, client_msg_id: str | None = None) -> JsonObject:
    return {
        "clientMsgId": client_msg_id or new_client_msg_id(),
        "payloadType": int(payload_type),
        "payload": payload,
    }


def build_application_auth_req(client_id: str, client_secret: str, client_msg_id: str | None = None) -> JsonObject:
    if not client_id or not client_secret:
        raise ValueError("clientId and clientSecret are required")
    return envelope(
        PayloadType.APPLICATION_AUTH_REQ,
        {"clientId": client_id, "clientSecret": client_secret},
        client_msg_id,
    )


def build_account_list_req(access_token: str, client_msg_id: str | None = None) -> JsonObject:
    if not access_token:
        raise ValueError("accessToken is required")
    return envelope(
        PayloadType.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
        {"accessToken": access_token},
        client_msg_id,
    )


def require_ctid(ctid_trader_account_id: int) -> int:
    if isinstance(ctid_trader_account_id, bool) or not isinstance(ctid_trader_account_id, int):
        raise ValueError("ctidTraderAccountId must be a positive integer")
    if ctid_trader_account_id <= 0:
        raise ValueError("ctidTraderAccountId must be a positive integer")
    return ctid_trader_account_id


def build_account_auth_req(
    access_token: str,
    ctid_trader_account_id: int,
    client_msg_id: str | None = None,
) -> JsonObject:
    if not access_token:
        raise ValueError("accessToken is required")
    return envelope(
        PayloadType.ACCOUNT_AUTH_REQ,
        {"ctidTraderAccountId": require_ctid(ctid_trader_account_id), "accessToken": access_token},
        client_msg_id,
    )


def build_reconcile_req(ctid_trader_account_id: int, client_msg_id: str | None = None) -> JsonObject:
    return envelope(
        PayloadType.RECONCILE_REQ,
        {
            "ctidTraderAccountId": require_ctid(ctid_trader_account_id),
            "returnProtectionOrders": False,
        },
        client_msg_id,
    )


def build_unrealized_pnl_req(ctid_trader_account_id: int, client_msg_id: str | None = None) -> JsonObject:
    return envelope(
        PayloadType.GET_POSITION_UNREALIZED_PNL_REQ,
        {"ctidTraderAccountId": require_ctid(ctid_trader_account_id)},
        client_msg_id,
    )


def require_position_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("positionId must be a positive integer")
    return value


def require_price(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite absolute price greater than 0")
    return number


def build_amend_position_sltp_req(
    *,
    ctid_trader_account_id: int,
    position_id: int,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    client_msg_id: str | None = None,
) -> JsonObject:
    """``ProtoOAAmendPositionSLTPReq`` (payloadType 2110).

    At least one of stop loss or take profit is required. Prices are absolute,
    as in the official examples (``1.23456``). ``ctid_trader_account_id`` is the
    id resolved from DEMO trader login 5360748, not the login itself.
    """

    if stop_loss is None and take_profit is None:
        raise ValueError(
            "Provide stopLoss and/or takeProfit. Refusing to send an empty ProtoOAAmendPositionSLTPReq."
        )
    payload: JsonObject = {
        "ctidTraderAccountId": require_ctid(ctid_trader_account_id),
        "positionId": require_position_id(position_id),
    }
    if stop_loss is not None:
        payload["stopLoss"] = require_price("stopLoss", stop_loss)
    if take_profit is not None:
        payload["takeProfit"] = require_price("takeProfit", take_profit)
    return envelope(PayloadType.AMEND_POSITION_SLTP_REQ, payload, client_msg_id)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def enum_name(value: Any, table: dict[int, str]) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or value is None:
        return str(value)
    try:
        return table.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def scale_money(raw: Any, digits: int) -> str | None:
    """Scale an integer monetary amount by ``10 ** moneyDigits``."""

    if raw is None:
        return None
    if isinstance(raw, bool):
        raise ApiError("BAD_MONEY", "Monetary value was a boolean.", 0)
    try:
        scaled = Decimal(int(raw)) / (Decimal(10) ** int(digits))
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ApiError("BAD_MONEY", "Monetary value could not be scaled.", 0) from exc
    return format(scaled, "f")


def volume_units(volume: Any) -> str | None:
    if volume is None:
        return None
    try:
        scaled = Decimal(int(volume)) / Decimal(100)
    except (TypeError, ValueError) as exc:
        raise ApiError("BAD_VOLUME", "Position volume could not be scaled.", 0) from exc
    return format(scaled.quantize(Decimal("0.01")), "f")


def _money_digits(payload: JsonObject, default: int | None = None) -> int | None:
    if "moneyDigits" not in payload or payload["moneyDigits"] is None:
        return default
    return int(payload["moneyDigits"])


def _is_open_status(status: Any) -> bool:
    if isinstance(status, bool):
        return False
    if status in OPEN_POSITION_STATUSES:
        return True
    if isinstance(status, str) and status.isdigit():
        return int(status) in OPEN_POSITION_STATUSES
    return False


def _bound_account(ctid: int) -> JsonObject:
    return {
        "accountId": ALLOWED_TRADER_LOGIN,
        "traderLogin": ALLOWED_TRADER_LOGIN,
        "ctidTraderAccountId": ctid,
        "host": ALLOWED_HOST,
        "endpoint": DEMO_WEBSOCKET_URL,
    }


def normalize_open_positions(
    reconcile: JsonObject,
    pnl_message: JsonObject,
    *,
    expected_ctid: int,
) -> JsonObject:
    """Merge ``ProtoOAReconcileRes`` with ``ProtoOAGetPositionUnrealizedPnLRes``."""

    reconcile_payload = reconcile.get("payload") or {}
    pnl_payload = pnl_message.get("payload") or {}
    ctid = assert_resolved_ctid(reconcile_payload.get("ctidTraderAccountId"), expected_ctid)
    assert_resolved_ctid(pnl_payload.get("ctidTraderAccountId"), expected_ctid)
    if "moneyDigits" not in pnl_payload:
        raise ApiError(
            "MISSING_MONEY_DIGITS",
            "ProtoOAGetPositionUnrealizedPnLRes.moneyDigits is required to scale floating P&L.",
            PayloadType.GET_POSITION_UNREALIZED_PNL_RES,
        )
    pnl_digits = int(pnl_payload["moneyDigits"])
    pnl_by_id: dict[int, JsonObject] = {}
    for entry in as_list(pnl_payload.get("positionUnrealizedPnL")):
        if not isinstance(entry, dict) or "positionId" not in entry:
            continue
        pnl_by_id[int(entry["positionId"])] = entry

    positions: list[JsonObject] = []
    for raw in as_list(reconcile_payload.get("position")):
        if not isinstance(raw, dict):
            continue
        status = raw.get("positionStatus")
        if not _is_open_status(status):
            continue
        if "positionId" not in raw:
            raise ApiError(
                "BAD_POSITION",
                "Open position is missing positionId.",
                PayloadType.RECONCILE_RES,
            )
        trade = raw.get("tradeData") or {}
        position_id = int(raw["positionId"])
        digits = _money_digits(raw)
        pnl = pnl_by_id.get(position_id)
        positions.append(
            {
                "positionId": position_id,
                "symbolId": None if trade.get("symbolId") is None else int(trade["symbolId"]),
                "tradeSide": enum_name(trade.get("tradeSide"), TRADE_SIDE_NAMES),
                "positionStatus": enum_name(status, POSITION_STATUS_NAMES),
                "volume": None if trade.get("volume") is None else int(trade["volume"]),
                "volumeUnits": volume_units(trade.get("volume")),
                "entryPrice": raw.get("price"),
                "stopLoss": raw.get("stopLoss"),
                "takeProfit": raw.get("takeProfit"),
                "swap": scale_money(raw.get("swap"), digits) if digits is not None else None,
                "commission": scale_money(raw.get("commission"), digits) if digits is not None else None,
                "usedMargin": scale_money(raw.get("usedMargin"), digits) if digits is not None else None,
                "moneyDigits": digits,
                "grossUnrealizedPnL": scale_money(pnl.get("grossUnrealizedPnL"), pnl_digits) if pnl else None,
                "netUnrealizedPnL": scale_money(pnl.get("netUnrealizedPnL"), pnl_digits) if pnl else None,
                "pnlMoneyDigits": pnl_digits,
                "label": trade.get("label"),
            }
        )
    return {
        **_bound_account(ctid),
        "positionCount": len(positions),
        "positions": positions,
    }


def execution_name(value: Any) -> str:
    if isinstance(value, str):
        return value
    return enum_name(value, EXECUTION_TYPE_NAMES)


def parse_amend_execution(
    message: JsonObject,
    *,
    requested_position_id: int,
    expected_ctid: int,
) -> JsonObject:
    payload = message.get("payload") or {}
    ctid = assert_resolved_ctid(payload.get("ctidTraderAccountId"), expected_ctid)
    name = execution_name(payload.get("executionType"))
    error_code = payload.get("errorCode") or None
    if error_code or name in REJECTED_EXECUTION_TYPES:
        detail = str(payload.get("description") or error_code or name)
        raise ApiError(str(error_code or name), detail, PayloadType.EXECUTION_EVENT)
    position = payload.get("position") or {}
    position_id = position.get("positionId", requested_position_id)
    return {
        **_bound_account(ctid),
        "positionId": int(position_id),
        "executionType": name,
        "stopLoss": position.get("stopLoss"),
        "takeProfit": position.get("takeProfit"),
        "errorCode": None,
    }
