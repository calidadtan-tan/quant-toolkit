"""Authorized DEMO session: app auth, account auth, read, amend SL/TP."""

from __future__ import annotations

import json
import time
from typing import Any, Iterable

from ctrader_demo.config import TradingConfig
from ctrader_demo.constants import (
    ALLOWED_ACCOUNT_ID,
    DEFAULT_TIMEOUT_SECONDS,
    ERROR_PAYLOAD_TYPES,
    VIEW_ONLY_SCOPES,
    PayloadType,
)
from ctrader_demo.errors import ApiError, DemoGuardError
from ctrader_demo.guards import assert_account_id, guard_outgoing_envelope, is_live_flag
from ctrader_demo.messages import (
    as_list,
    build_account_auth_req,
    build_account_list_req,
    build_amend_position_sltp_req,
    build_application_auth_req,
    build_reconcile_req,
    build_unrealized_pnl_req,
    normalize_open_positions,
    parse_amend_execution,
)

JsonObject = dict[str, Any]


class DemoClient:
    def __init__(self, config: TradingConfig, transport: Any, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        if config.account_id != ALLOWED_ACCOUNT_ID:
            assert_account_id(config.account_id)
        if config.host != "demo.ctraderapi.com" or config.port != 5036:
            raise DemoGuardError(
                "DEMO GUARD: TradingConfig is not bound to demo.ctraderapi.com:5036."
            )
        self.config = config
        self.transport = transport
        self.timeout = timeout
        self.permission_scope: Any = None

    def connect(self) -> None:
        if self.config.host != "demo.ctraderapi.com":
            raise DemoGuardError("DEMO GUARD: refusing to connect because host is not demo.ctraderapi.com.")
        self.transport.connect()

    def close(self) -> None:
        closer = getattr(self.transport, "close", None)
        if closer is not None:
            closer()

    def send(self, envelope: JsonObject) -> None:
        guard_outgoing_envelope(envelope)
        self.transport.send_text(json.dumps(envelope, separators=(",", ":"), ensure_ascii=False))

    def request(self, envelope: JsonObject, *, expect: Iterable[int], require_account: bool) -> JsonObject:
        self.send(envelope)
        expect_set = set(expect)
        msg_id = envelope["clientMsgId"]
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ApiError(
                    "TIMEOUT",
                    f"No response for payloadType {envelope['payloadType']} within {self.timeout}s. "
                    "This does not mean the request succeeded.",
                    int(envelope["payloadType"]),
                )
            raw = self.transport.recv_text(remaining)
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ApiError("BAD_JSON", "Proxy returned a non-JSON frame.", int(envelope["payloadType"])) from exc
            if not isinstance(message, dict) or "payloadType" not in message:
                raise ApiError("BAD_JSON", "Proxy JSON is missing payloadType.", int(envelope["payloadType"]))
            payload_type = int(message["payloadType"])
            incoming_id = message.get("clientMsgId")
            if payload_type == PayloadType.HEARTBEAT_EVENT:
                continue
            if incoming_id not in (None, msg_id):
                continue
            if payload_type in ERROR_PAYLOAD_TYPES:
                self._raise_api_error(message)
            if payload_type in expect_set:
                self._require_response_account(message, required=require_account)
                return message
            if incoming_id == msg_id:
                raise ApiError(
                    "UNEXPECTED",
                    f"Unexpected payloadType {payload_type} for this request.",
                    payload_type,
                )

    def authorize(self) -> None:
        self.request(
            build_application_auth_req(self.config.client_id, self.config.client_secret),
            expect={PayloadType.APPLICATION_AUTH_RES},
            require_account=False,
        )
        listed = self.request(
            build_account_list_req(self.config.access_token),
            expect={PayloadType.GET_ACCOUNTS_BY_ACCESS_TOKEN_RES},
            require_account=False,
        )
        self._accept_account_list(listed)
        authed = self.request(
            build_account_auth_req(self.config.access_token),
            expect={PayloadType.ACCOUNT_AUTH_RES},
            require_account=True,
        )
        self._require_response_account(authed, required=True)

    def read_positions(self) -> JsonObject:
        reconcile = self.request(
            build_reconcile_req(),
            expect={PayloadType.RECONCILE_RES},
            require_account=True,
        )
        pnl = self.request(
            build_unrealized_pnl_req(),
            expect={PayloadType.GET_POSITION_UNREALIZED_PNL_RES},
            require_account=True,
        )
        return normalize_open_positions(reconcile, pnl)

    def amend_sltp(self, *, position_id: int, stop_loss: float | None, take_profit: float | None) -> JsonObject:
        if self.permission_scope in VIEW_ONLY_SCOPES:
            raise DemoGuardError(
                "DEMO GUARD: access token scope is view-only (accounts). "
                "Refusing to send ProtoOAAmendPositionSLTPReq. Re-authorize with scope=trading."
            )
        envelope = build_amend_position_sltp_req(
            position_id=position_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        event = self.request(
            envelope,
            expect={PayloadType.EXECUTION_EVENT},
            require_account=True,
        )
        return parse_amend_execution(event, requested_position_id=position_id)

    def _accept_account_list(self, message: JsonObject) -> None:
        payload = message.get("payload") or {}
        self.permission_scope = payload.get("permissionScope")
        match = None
        for account in as_list(payload.get("ctidTraderAccount")):
            if not isinstance(account, dict) or "ctidTraderAccountId" not in account:
                continue
            try:
                account_id = int(account["ctidTraderAccountId"])
            except (TypeError, ValueError):
                continue
            if account_id != ALLOWED_ACCOUNT_ID:
                continue
            match = account
            break
        if match is None:
            raise DemoGuardError(
                "DEMO GUARD: DEMO account 5360748 is not granted to this access token. "
                "Refusing to authorize any other account."
            )
        if is_live_flag(match.get("isLive")):
            raise DemoGuardError(
                "DEMO GUARD: account 5360748 is marked isLive=true. "
                "Refusing before ProtoOAAccountAuthReq and before any trading request."
            )

    def _require_response_account(self, message: JsonObject, *, required: bool) -> None:
        payload = message.get("payload") or {}
        if "ctidTraderAccountId" not in payload:
            if required:
                raise DemoGuardError(
                    "DEMO GUARD: response omitted ctidTraderAccountId. Refusing to continue."
                )
            return
        assert_account_id(payload["ctidTraderAccountId"])

    def _raise_api_error(self, message: JsonObject) -> None:
        payload = message.get("payload") or {}
        code = str(payload.get("errorCode") or "OA_ERROR")
        description = self.config.redact(str(payload.get("description") or ""))
        raise ApiError(code, description, int(message["payloadType"]))
