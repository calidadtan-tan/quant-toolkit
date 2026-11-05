"""Command line for the DEMO-only client."""

from __future__ import annotations

import argparse

from ctrader_demo.config import enforce_demo_env, load_trading_config, optional_env
from ctrader_demo.constants import (
    ALLOWED_REDIRECT_URI,
    ENV_ACCESS_TOKEN,
    ENV_CLIENT_ID,
    ENV_CLIENT_SECRET,
    ENV_REDIRECT_URI,
    ENV_REFRESH_TOKEN,
    OPEN_API_APP_NAME,
    OPEN_API_APP_STATUS,
)
from ctrader_demo.errors import ApiError, ConfigError, DemoGuardError, UsageError
from ctrader_demo.report import emit_report, failure_report, success_report
from ctrader_demo.oauth import (
    assert_public_redirect,
    build_authorize_url,
    build_token_request,
    fetch_token,
    secure_urlopen,
)
from ctrader_demo.session import DemoClient
from ctrader_demo.transport import SslWebSocketTransport


class BotArgumentParser(argparse.ArgumentParser):
    """Raise UsageError instead of printing text and calling sys.exit."""

    def error(self, message: str) -> None:
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = BotArgumentParser(
        prog="python -m ctrader_demo",
        description="DEMO-only cTrader Open API client for account 5360748 on demo.ctraderapi.com.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("read-positions", help="Read open positions and floating P&L for account 5360748")

    amend = sub.add_parser(
        "amend-sl",
        help="Amend stop loss / take profit via ProtoOAAmendPositionSLTPReq",
    )
    amend.add_argument("--position-id", type=int, required=True)
    amend.add_argument("--stop-loss", type=float, default=None)
    amend.add_argument("--take-profit", type=float, default=None)

    auth = sub.add_parser("auth-url", help="Print the Spotware OAuth authorize URL")
    auth.add_argument("--redirect-uri", default=None)
    auth.add_argument("--scope", default="trading", choices=["trading", "accounts"])

    exchange = sub.add_parser("exchange-code", help="Exchange an OAuth authorization code for tokens")
    exchange.add_argument("--code", default=None)
    exchange.add_argument("--redirect-uri", default=None)

    sub.add_parser("refresh-token", help="Refresh CTRADER_ACCESS_TOKEN using CTRADER_REFRESH_TOKEN")
    return parser


def _redirect(explicit: str | None) -> str:
    value = (explicit or optional_env(ENV_REDIRECT_URI) or ALLOWED_REDIRECT_URI).strip()
    return assert_public_redirect(value)


def _cmd_auth_url(args: argparse.Namespace) -> int:
    client_id = optional_env(ENV_CLIENT_ID)
    if not client_id:
        raise ConfigError(
            f"Missing environment variable {ENV_CLIENT_ID}. "
            f"Open API app {OPEN_API_APP_NAME} is Status={OPEN_API_APP_STATUS} (not Active). "
            "Do not hardcode the client id."
        )
    redirect_uri = _redirect(args.redirect_uri)
    url = build_authorize_url(client_id=client_id, redirect_uri=redirect_uri, scope=args.scope)
    result = {"url": url}
    if args.scope == "accounts":
        result["warning"] = "scope=accounts cannot amend stop loss. Use scope=trading for amend-sl."
    return result


def _cmd_exchange(args: argparse.Namespace, *, urlopen) -> int:
    code = (args.code or "").strip()
    if not code:
        raise ConfigError(
            "Missing authorization code (--code). "
            f"Open API app {OPEN_API_APP_NAME} is Status={OPEN_API_APP_STATUS} (not Active). "
            "OAuth cannot issue a code until Spotware activates the app. Do not hardcode a token."
        )
    request = build_token_request(
        grant_type="authorization_code",
        client_id=_env_required(ENV_CLIENT_ID),
        client_secret=_env_required(ENV_CLIENT_SECRET),
        code=code,
        redirect_uri=_redirect(args.redirect_uri),
    )
    tokens = fetch_token(request, urlopen=urlopen)
    tokens["hint"] = (
        f"Store accessToken and refreshToken in the gitignored .env as {ENV_ACCESS_TOKEN} and "
        f"{ENV_REFRESH_TOKEN}. Do not commit them."
    )
    return tokens


def _cmd_refresh(*, urlopen) -> int:
    request = build_token_request(
        grant_type="refresh_token",
        client_id=_env_required(ENV_CLIENT_ID),
        client_secret=_env_required(ENV_CLIENT_SECRET),
        refresh_token=_env_required(ENV_REFRESH_TOKEN),
    )
    tokens = fetch_token(request, urlopen=urlopen)
    tokens["hint"] = (
        f"Replace {ENV_ACCESS_TOKEN} and {ENV_REFRESH_TOKEN} with these new values. "
        "The previous pair is invalidated. Do not commit them."
    )
    return tokens


def _env_required(name: str) -> str:
    value = optional_env(name)
    if not value:
        raise ConfigError(
            f"Missing environment variable {name}. "
            f"Open API app {OPEN_API_APP_NAME} is Status={OPEN_API_APP_STATUS} (not Active). "
            "Tokens stay empty until Spotware activates the app and OAuth completes. "
            "Do not hardcode or commit secrets."
        )
    return value


def _validate_amend(args: argparse.Namespace) -> None:
    if args.stop_loss is None and args.take_profit is None:
        raise ValueError(
            "Provide --stop-loss and/or --take-profit. "
            "Refusing to send an empty ProtoOAAmendPositionSLTPReq."
        )


def execute(argv: list[str] | None = None, *, transport_factory=SslWebSocketTransport, urlopen=secure_urlopen) -> dict:
    """Run one command and return the report dict. Does not print."""

    command: str | None = None
    try:
        args = build_parser().parse_args(argv)
        command = args.command
        enforce_demo_env()
        if args.command == "auth-url":
            result = _cmd_auth_url(args)
        elif args.command == "exchange-code":
            result = _cmd_exchange(args, urlopen=urlopen)
        elif args.command == "refresh-token":
            result = _cmd_refresh(urlopen=urlopen)
        else:
            config = load_trading_config()
            if args.command == "amend-sl":
                _validate_amend(args)
            transport = transport_factory()
            client = DemoClient(config, transport)
            try:
                client.connect()
                client.authorize()
                if args.command == "read-positions":
                    result = client.read_positions()
                elif args.command == "amend-sl":
                    result = client.amend_sltp(
                        position_id=args.position_id,
                        stop_loss=args.stop_loss,
                        take_profit=args.take_profit,
                    )
                else:
                    raise ConfigError(f"Unknown command {args.command}")
            finally:
                client.close()
        return success_report(command, result)
    except DemoGuardError as exc:
        return failure_report(2, "DEMO_GUARD", str(exc), command)
    except ConfigError as exc:
        return failure_report(1, "CONFIG", str(exc), command)
    except ApiError as exc:
        return failure_report(1, "API", str(exc), command)
    except (UsageError, ValueError) as exc:
        return failure_report(1, "USAGE", str(exc), command)
    except Exception as exc:
        return failure_report(1, "INTERNAL", str(exc), command)


def main(argv: list[str] | None = None, *, transport_factory=SslWebSocketTransport, urlopen=secure_urlopen) -> int:
    return emit_report(execute(argv, transport_factory=transport_factory, urlopen=urlopen))


def console_main() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    console_main()
