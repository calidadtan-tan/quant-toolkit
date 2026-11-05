"""Official cTrader Open API identifiers used by this DEMO client.

Payload numbers are ``ProtoOAPayloadType`` / ``ProtoPayloadType`` values from
https://github.com/spotware/openapi-proto-messages
"""

ALLOWED_HOST = "demo.ctraderapi.com"
ALLOWED_JSON_PORT = 5036
ALLOWED_ACCOUNT_ID = 5360748
ALLOWED_REDIRECT_URI = "https://localhost"

# Spotware Open API application. Status is Submitted, not Active, so OAuth
# tokens do not exist yet. Never hardcode the client id, secret, or tokens.
OPEN_API_APP_NAME = "poteto-demo-sltp"
OPEN_API_APP_STATUS = "Submitted"

ENV_HOST = "CTRADER_HOST"
ENV_ACCOUNT_ID = "CTRADER_ACCOUNT_ID"
ENV_CLIENT_ID = "CTRADER_CLIENT_ID"
ENV_CLIENT_SECRET = "CTRADER_CLIENT_SECRET"
ENV_ACCESS_TOKEN = "CTRADER_ACCESS_TOKEN"
ENV_REFRESH_TOKEN = "CTRADER_REFRESH_TOKEN"
ENV_REDIRECT_URI = "CTRADER_REDIRECT_URI"

# Trading sockets. ``connect()`` uses the demo literal and refuses anything else.
DEMO_WEBSOCKET_URL = "wss://demo.ctraderapi.com:5036"

# OAuth only. This host does not accept trading messages.
TOKEN_ENDPOINT = "https://openapi.ctrader.com/apps/token"
AUTHORIZE_ENDPOINT = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"

# Hosts that must never be dialed. Matched case-insensitively.
FORBIDDEN_HOST_MARKERS = (
    "live.ctraderapi.com",
    "live.p.ctrader.com",
    "live1.p.ctrader.com",
    "live2.p.ctrader.com",
)


class PayloadType:
    """Numeric ``payloadType`` values from the Open API proto enums."""

    ERROR_RES = 50  # ProtoPayloadType.ERROR_RES
    HEARTBEAT_EVENT = 51  # ProtoPayloadType.HEARTBEAT_EVENT

    APPLICATION_AUTH_REQ = 2100  # PROTO_OA_APPLICATION_AUTH_REQ
    APPLICATION_AUTH_RES = 2101
    ACCOUNT_AUTH_REQ = 2102
    ACCOUNT_AUTH_RES = 2103
    NEW_ORDER_REQ = 2106
    CANCEL_ORDER_REQ = 2108
    AMEND_ORDER_REQ = 2109
    AMEND_POSITION_SLTP_REQ = 2110  # PROTO_OA_AMEND_POSITION_SLTP_REQ
    CLOSE_POSITION_REQ = 2111
    RECONCILE_REQ = 2124
    RECONCILE_RES = 2125
    EXECUTION_EVENT = 2126
    ORDER_ERROR_EVENT = 2132
    OA_ERROR_RES = 2142
    GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
    GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150
    GET_POSITION_UNREALIZED_PNL_REQ = 2187
    GET_POSITION_UNREALIZED_PNL_RES = 2188


# The only application messages this process is allowed to send.
ALLOWED_OUTGOING_PAYLOAD_TYPES = frozenset(
    {
        PayloadType.APPLICATION_AUTH_REQ,
        PayloadType.ACCOUNT_AUTH_REQ,
        PayloadType.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
        PayloadType.RECONCILE_REQ,
        PayloadType.GET_POSITION_UNREALIZED_PNL_REQ,
        PayloadType.AMEND_POSITION_SLTP_REQ,
    }
)

ERROR_PAYLOAD_TYPES = frozenset(
    {
        PayloadType.ERROR_RES,
        PayloadType.OA_ERROR_RES,
        PayloadType.ORDER_ERROR_EVENT,
    }
)

ACCOUNT_BOUND_PAYLOAD_TYPES = frozenset(
    {
        PayloadType.ACCOUNT_AUTH_REQ,
        PayloadType.RECONCILE_REQ,
        PayloadType.GET_POSITION_UNREALIZED_PNL_REQ,
        PayloadType.AMEND_POSITION_SLTP_REQ,
    }
)

EXECUTION_TYPE_NAMES = {
    2: "ORDER_ACCEPTED",
    3: "ORDER_FILLED",
    4: "ORDER_REPLACED",
    5: "ORDER_CANCELLED",
    6: "ORDER_EXPIRED",
    7: "ORDER_REJECTED",
    8: "ORDER_CANCEL_REJECTED",
    9: "SWAP",
    10: "DEPOSIT_WITHDRAW",
    11: "ORDER_PARTIAL_FILL",
    12: "BONUS_DEPOSIT_WITHDRAW",
}

REJECTED_EXECUTION_TYPES = frozenset({"ORDER_REJECTED", "ORDER_CANCEL_REJECTED"})

TRADE_SIDE_NAMES = {1: "BUY", 2: "SELL"}

POSITION_STATUS_NAMES = {
    1: "POSITION_STATUS_OPEN",
    2: "POSITION_STATUS_CLOSED",
    3: "POSITION_STATUS_CREATED",
    4: "POSITION_STATUS_ERROR",
}

OPEN_POSITION_STATUSES = frozenset({1, "POSITION_STATUS_OPEN", "OPEN"})

VIEW_ONLY_SCOPES = frozenset({0, "0", "SCOPE_VIEW", "VIEW"})

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME_BYTES = 2_000_000
DEFAULT_TIMEOUT_SECONDS = 20.0
