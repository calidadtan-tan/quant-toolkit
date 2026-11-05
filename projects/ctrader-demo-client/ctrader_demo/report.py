"""One-line JSON report for the quant bot.

stdout is always one JSON object with ``code`` and ``message``.
On failure, stderr is the same line. On success, stderr is empty.
"""

from __future__ import annotations

import json
import sys
from typing import Any

JsonObject = dict[str, Any]


def success_report(command: str, result: JsonObject) -> JsonObject:
    return {
        "ok": True,
        "code": 0,
        "error": None,
        "command": command,
        "message": "ok",
        "result": result,
    }


def failure_report(code: int, error: str, message: str, command: str | None) -> JsonObject:
    text = " ".join(str(message).split())
    return {
        "ok": False,
        "code": int(code),
        "error": error,
        "command": command,
        "message": text,
    }


def dumps_report(report: JsonObject) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def emit_report(report: JsonObject) -> int:
    line = dumps_report(report)
    sys.stdout.write(line)
    if int(report["code"]) != 0:
        sys.stderr.write(line)
    return int(report["code"])
