"""Environment loading. Secrets stay in the process environment or a gitignored .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ctrader_demo.constants import (
    ALLOWED_ACCOUNT_ID,
    ALLOWED_HOST,
    ALLOWED_JSON_PORT,
    ENV_ACCESS_TOKEN,
    ENV_ACCOUNT_ID,
    ENV_CLIENT_ID,
    ENV_CLIENT_SECRET,
    ENV_HOST,
    ENV_REFRESH_TOKEN,
    OPEN_API_APP_NAME,
    OPEN_API_APP_STATUS,
)
from ctrader_demo.errors import ConfigError, DemoGuardError
from ctrader_demo.guards import assert_account_id, assert_demo_host

def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse a subset of dotenv syntax. Existing environment variables win."""

    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def find_dotenv() -> Path | None:
    cwd_file = Path.cwd() / ".env"
    if cwd_file.is_file():
        return cwd_file
    packaged = package_root() / ".env"
    if packaged.is_file() and packaged != cwd_file:
        return packaged
    return None


def load_dotenv() -> Path | None:
    path = find_dotenv()
    if path is None:
        return None
    parsed = parse_dotenv(path.read_text(encoding="utf-8"))
    for key, value in parsed.items():
        os.environ.setdefault(key, value)
    return path


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing environment variable {name}. "
            f"Open API app {OPEN_API_APP_NAME} is Status={OPEN_API_APP_STATUS} (not Active). "
            "Access and refresh tokens stay empty until Spotware activates the app and OAuth completes. "
            "Put values in the environment or a gitignored .env file. Do not hardcode or commit secrets."
        )
    return value


def enforce_demo_env() -> int:
    """Check host and account before any command does I/O.

    Missing or foreign ``CTRADER_ACCOUNT_ID`` is a guard failure, not a prompt to
    pick another account. The JSON port is fixed at 5036 and is not configurable.
    """

    load_dotenv()
    host = os.environ.get(ENV_HOST, "").strip() or ALLOWED_HOST
    assert_demo_host(host)
    account_raw = os.environ.get(ENV_ACCOUNT_ID, "").strip()
    if not account_raw:
        raise DemoGuardError(
            f"DEMO GUARD: {ENV_ACCOUNT_ID} is missing. This client only accepts DEMO account "
            f"{ALLOWED_ACCOUNT_ID}."
        )
    return assert_account_id(account_raw)


@dataclass(frozen=True)
class TradingConfig:
    client_id: str
    client_secret: str
    access_token: str
    account_id: int
    host: str
    port: int
    refresh_token: str

    def redact(self, text: str) -> str:
        redacted = text
        for secret in (self.access_token, self.client_secret, self.client_id, self.refresh_token):
            if secret:
                redacted = redacted.replace(secret, "***")
        return redacted


def load_trading_config() -> TradingConfig:
    account_id = enforce_demo_env()
    return TradingConfig(
        client_id=_required(ENV_CLIENT_ID),
        client_secret=_required(ENV_CLIENT_SECRET),
        access_token=_required(ENV_ACCESS_TOKEN),
        account_id=account_id,
        host=assert_demo_host(os.environ.get(ENV_HOST, "").strip() or ALLOWED_HOST),
        port=ALLOWED_JSON_PORT,
        refresh_token=os.environ.get(ENV_REFRESH_TOKEN, "").strip(),
    )


def optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()
