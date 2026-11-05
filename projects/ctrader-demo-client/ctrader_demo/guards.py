"""Fail closed before any trading request leaves the process."""

from __future__ import annotations

from ctrader_demo.constants import (
    ACCOUNT_BOUND_PAYLOAD_TYPES,
    ALLOWED_HOST,
    ALLOWED_JSON_PORT,
    ALLOWED_OUTGOING_PAYLOAD_TYPES,
    ALLOWED_TRADER_LOGIN,
    FORBIDDEN_HOST_MARKERS,
    LOGIN_FIELD_NAMES,
)
from ctrader_demo.errors import DemoGuardError


def assert_not_forbidden_host(host: str) -> None:
    """Reject live proxy hostnames.

    A host that merely contains the substring ``live`` inside another word is
    left to :func:`assert_demo_host`. This check is for known live proxies and
    for any hostname that starts with ``live``.
    """

    lowered = host.strip().lower().rstrip(".")
    if lowered.startswith("live") or any(marker in lowered for marker in FORBIDDEN_HOST_MARKERS):
        raise DemoGuardError(
            "DEMO GUARD: refusing host "
            f"{host.strip()!r}. This client never connects to live endpoints "
            "(including live.ctraderapi.com). The only allowed trading host is "
            "demo.ctraderapi.com."
        )


def assert_demo_host(host: str) -> str:
    """Return the demo hostname, or raise before a connection is opened."""

    if not isinstance(host, str) or not host.strip():
        raise DemoGuardError(
            "DEMO GUARD: host is missing. The only allowed trading host is demo.ctraderapi.com."
        )
    normalized = host.strip().lower().rstrip(".")
    assert_not_forbidden_host(normalized)
    if normalized != ALLOWED_HOST:
        raise DemoGuardError(
            f"DEMO GUARD: refusing host {host.strip()!r}. "
            "This client only connects to demo.ctraderapi.com."
        )
    return ALLOWED_HOST


def assert_demo_port(port: int | str) -> int:
    try:
        value = int(port)
    except (TypeError, ValueError) as exc:
        raise DemoGuardError(
            f"DEMO GUARD: refusing port {port!r}. JSON demo endpoint is port {ALLOWED_JSON_PORT} only."
        ) from exc
    if value != ALLOWED_JSON_PORT:
        raise DemoGuardError(
            f"DEMO GUARD: refusing port {value}. JSON demo endpoint is port {ALLOWED_JSON_PORT} only. "
            "Port 5035 (Protobuf) and every live port are refused."
        )
    return value


def _parse_strict_int(value: object, *, what: str) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise DemoGuardError(
            f"DEMO GUARD: refusing {what} {value!r}. "
            f"This client is bound to DEMO trader login {ALLOWED_TRADER_LOGIN} only."
        )
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise DemoGuardError(
            f"DEMO GUARD: refusing {what} {value!r}. "
            f"This client is bound to DEMO trader login {ALLOWED_TRADER_LOGIN} only."
        ) from exc


def assert_account_id(account_id: int | str) -> int:
    """Accept only DEMO trader login 5360748.

    ``CTRADER_ACCOUNT_ID`` is the cTrader login (``traderLogin``), not
    ``ctidTraderAccountId``.
    """

    value = _parse_strict_int(account_id, what="accountId")
    if value != ALLOWED_TRADER_LOGIN:
        raise DemoGuardError(
            f"DEMO GUARD: refusing accountId {value}. "
            f"This client is bound to DEMO trader login {ALLOWED_TRADER_LOGIN} only and will not "
            "send trading requests for any other account."
        )
    return value


def assert_resolved_ctid(ctid: object, expected: int) -> int:
    """Accept only the ctid resolved from DEMO trader login 5360748."""

    if expected <= 0:
        raise DemoGuardError(
            "DEMO GUARD: refusing to send a trading request before DEMO trader login "
            f"{ALLOWED_TRADER_LOGIN} was resolved to a ctidTraderAccountId."
        )
    value = _parse_strict_int(ctid, what="ctidTraderAccountId")
    if value != expected:
        raise DemoGuardError(
            f"DEMO GUARD: refusing ctidTraderAccountId {value}. "
            f"This process may only use ctid {expected}, resolved from DEMO trader login "
            f"{ALLOWED_TRADER_LOGIN}."
        )
    return value


def trader_login_of(account: dict) -> int | None:
    """Read traderLogin, or a fixture alias, from one account-list entry."""

    if not isinstance(account, dict):
        return None
    for key in LOGIN_FIELD_NAMES:
        if key not in account or account[key] is None:
            continue
        try:
            return _parse_strict_int(account[key], what=key)
        except DemoGuardError:
            return None
    return None


def ctid_of(account: dict) -> int | None:
    if not isinstance(account, dict) or "ctidTraderAccountId" not in account:
        return None
    try:
        value = _parse_strict_int(account["ctidTraderAccountId"], what="ctidTraderAccountId")
    except DemoGuardError:
        return None
    if value <= 0:
        return None
    return value


def is_live_flag(value: object) -> bool:
    """True when an account-list entry says the account belongs to Live."""

    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
        return True
    return False


def guard_outgoing_envelope(envelope: dict, *, resolved_ctid: int | None) -> None:
    """Reject anything that is not a demo read or SL/TP amend for the resolved ctid.

    Account-bound payloads must use the ``ctidTraderAccountId`` resolved from
    DEMO trader login 5360748. Called immediately before the frame is written.
    """

    if not isinstance(envelope, dict):
        raise DemoGuardError("DEMO GUARD: refusing a non-object Open API message.")
    try:
        payload_type = int(envelope["payloadType"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DemoGuardError("DEMO GUARD: outgoing message is missing payloadType.") from exc
    if payload_type not in ALLOWED_OUTGOING_PAYLOAD_TYPES:
        raise DemoGuardError(
            f"DEMO GUARD: refusing payloadType {payload_type}. "
            "This client may only authorize, read positions, read floating P&L, "
            f"and send ProtoOAAmendPositionSLTPReq (2110) for DEMO trader login {ALLOWED_TRADER_LOGIN}."
        )
    payload = envelope.get("payload") or {}
    if not isinstance(payload, dict):
        raise DemoGuardError("DEMO GUARD: outgoing payload must be an object.")
    if payload_type in ACCOUNT_BOUND_PAYLOAD_TYPES or "ctidTraderAccountId" in payload:
        if resolved_ctid is None:
            raise DemoGuardError(
                "DEMO GUARD: refusing ctidTraderAccountId before DEMO trader login "
                f"{ALLOWED_TRADER_LOGIN} was resolved from the account list."
            )
        if "ctidTraderAccountId" not in payload:
            raise DemoGuardError(
                f"DEMO GUARD: payloadType {payload_type} is missing ctidTraderAccountId."
            )
        assert_resolved_ctid(payload["ctidTraderAccountId"], resolved_ctid)
