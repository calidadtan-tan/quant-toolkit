"""Load the approved cTrader DEMO env file and forward argv to ctrader_demo.

Zero-fill: this file contains no tokens. Credentials are read from an env file
that must already exist on the machine:

    %LOCALAPPDATA%\\Temp\\ctrader-demo-secure\\ctrader-openapi-46950-demo.env

If that file is missing, ask the bot or user who holds it for an approved copy.
Never write secrets into git, a PR, SKILL.md, README, or a sample .env.
DEMO only. The known Live account is refused.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

ENV_FILENAME = "ctrader-openapi-46950-demo.env"
ENV_DIR_PARTS = ("Temp", "ctrader-demo-secure")
DEMO_HOST = "demo.ctraderapi.com"
LIVE_ACCOUNT_IDS = frozenset({"1401957"})
DEMO_ACCOUNT_DEFAULT = "5360748"

REQUIRED_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CTRADER_CLIENT_ID", ("CTRADER_CLIENT_ID", "CLIENT_ID")),
    (
        "SECRET",
        ("CTRADER_CLIENT_SECRET", "CTRADER_SECRET", "CLIENT_SECRET", "SECRET"),
    ),
    ("ACCESS_TOKEN", ("CTRADER_ACCESS_TOKEN", "ACCESS_TOKEN")),
    ("REFRESH_TOKEN", ("CTRADER_REFRESH_TOKEN", "REFRESH_TOKEN")),
    ("ACCOUNT_ID", ("CTRADER_ACCOUNT_ID", "ACCOUNT_ID")),
    ("HOST", ("CTRADER_HOST", "HOST")),
)

ACCOUNT_KEYS = ("CTRADER_ACCOUNT_ID", "ACCOUNT_ID")
HOST_KEYS = ("CTRADER_HOST", "HOST")
STRIP_KEYS = tuple(key for _, keys in REQUIRED_GROUPS for key in keys)

MISSING_ENV_MESSAGE = """\
缺少已批准嘅 DEMO env 檔。零填寫前提未滿足。

約定路徑：
  %LOCALAPPDATA%\\Temp\\ctrader-demo-secure\\ctrader-openapi-46950-demo.env

請向持有該 env 嘅 bot／用戶索取已批准副本，放到上述路徑。
若副本已在其他已批准嘅 vault／Copy 路徑，設 CTRADER_DEMO_ENV_FILE 指向該現成檔（只係路徑）。
唔好把 ACCESS_TOKEN、REFRESH_TOKEN、CLIENT_SECRET 或任何 token 寫入 git、PR、SKILL、README、示範 .env 或聊天。
本腳本唔會要求你喺命令列填寫 token。
"""

PERMISSION_MESSAGE = (
    "env 檔權限過寬。請收成只限本用戶可讀（POSIX 例：chmod 600；Windows 用只讀 ACL）。"
    "唔好把檔案內容貼去聊天或 git。"
)


class Prepared:
    def __init__(
        self,
        code: int,
        message: str,
        source: str,
        child_env: dict[str, str] | None,
        account_id: str,
        host: str,
    ) -> None:
        self.code = code
        self.message = message
        self.source = source
        self.child_env = child_env
        self.account_id = account_id
        self.host = host


def agreed_env_path(parent: Mapping[str, str]) -> Path | None:
    local = parent.get("LOCALAPPDATA", "").strip()
    if not local:
        return None
    return Path(local).joinpath(*ENV_DIR_PARTS, ENV_FILENAME)


def resolve_env_path(parent: Mapping[str, str]) -> tuple[Path | None, str]:
    override = parent.get("CTRADER_DEMO_ENV_FILE", "").strip()
    if override:
        path = Path(override)
        if path.is_file():
            return path, "approved-copy"
    agreed = agreed_env_path(parent)
    if agreed is not None and agreed.is_file():
        return agreed, "agreed-path"
    return None, ""


def permissions_ok(path: Path) -> bool:
    if os.name == "nt":
        return True
    return path.stat().st_mode & 0o077 == 0


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = path.read_text(encoding="utf-8-sig")
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ValueError(f"第 {lineno} 行唔係 KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise ValueError(f"第 {lineno} 行 key 無效")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _nonempty(values: Mapping[str, str], keys: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for key in keys:
        value = values.get(key, "").strip()
        if value and value not in found:
            found.append(value)
    return found


def demo_guard(values: Mapping[str, str]) -> tuple[int, str]:
    accounts = _nonempty(values, ACCOUNT_KEYS)
    if any(account in LIVE_ACCOUNT_IDS for account in accounts):
        return (
            2,
            "DEMO_GUARD: 偵測到 Live 帳戶 1401957，已停止。只允許 DEMO。請通報。",
        )
    hosts = [host.lower().rstrip(".") for host in _nonempty(values, HOST_KEYS)]
    if any(host != DEMO_HOST or "live" in host for host in hosts):
        return (
            2,
            "DEMO_GUARD: HOST 唔係 demo.ctraderapi.com，已停止。只允許 DEMO。",
        )
    if len(accounts) > 1:
        return 1, "env 檔 ACCOUNT_ID 多個鍵不一致，已停止。唔好喺聊天貼 token。"
    if len(hosts) > 1:
        return 1, "env 檔 HOST 多個鍵不一致，已停止。只允許 demo.ctraderapi.com。"
    missing = [
        label
        for label, keys in REQUIRED_GROUPS
        if not any(values.get(key, "").strip() for key in keys)
    ]
    if missing:
        names = "、".join(missing)
        return (
            1,
            "env 檔缺少已批准欄位："
            + names
            + "。請向持有人索取完整副本。唔好喺 git 或聊天補 token。",
        )
    return 0, ""


def prepare(parent: Mapping[str, str]) -> Prepared:
    path, source = resolve_env_path(parent)
    if path is None:
        return Prepared(1, MISSING_ENV_MESSAGE, "", None, "", "")
    if not permissions_ok(path):
        return Prepared(1, PERMISSION_MESSAGE, source, None, "", "")
    try:
        values = load_env(path)
    except ValueError as exc:
        return Prepared(1, f"env 檔格式錯誤：{exc}", source, None, "", "")
    code, message = demo_guard(values)
    if code != 0:
        return Prepared(code, message, source, None, "", "")
    child = dict(parent)
    for key in STRIP_KEYS:
        child.pop(key, None)
    child.update(values)
    return Prepared(
        0,
        "",
        source,
        child,
        _nonempty(values, ACCOUNT_KEYS)[0],
        _nonempty(values, HOST_KEYS)[0],
    )


def build_command(args: list[str]) -> list[str]:
    return [sys.executable, "-m", "ctrader_demo", *args]


def main(argv: list[str] | None = None, parent: Mapping[str, str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if parent is None else parent
    prepared = prepare(env)
    if prepared.code != 0:
        print(prepared.message, file=sys.stderr)
        return prepared.code
    if not args or args == ["--help"]:
        print(
            "用法：python run_ctrader_demo.py --check | read-positions | "
            "amend-sl | open-market | close-position ...",
            file=sys.stderr,
        )
        return 1
    if args == ["--check"]:
        print(
            json.dumps(
                {
                    "code": 0,
                    "mode": "check",
                    "accountId": prepared.account_id,
                    "host": prepared.host,
                    "envSource": prepared.source,
                    "demoDefault": DEMO_ACCOUNT_DEFAULT,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if prepared.child_env is None:
        print(MISSING_ENV_MESSAGE, file=sys.stderr)
        return 1
    completed = subprocess.run(
        build_command(args),
        env=prepared.child_env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
