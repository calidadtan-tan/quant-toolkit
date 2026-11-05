"""DEMO-only cTrader Open API client.

This package connects only to ``demo.ctraderapi.com`` and only to DEMO
account ``5360748``. It will not open a live trading socket.

Quant-bot entrypoints (they return the report dict and do not print):

- ``read_positions()``
- ``amend_sltp(position_id, stop_loss=None, take_profit=None)``

CLI equivalents, from ``projects/ctrader-demo-client``:

- ``python3 -m ctrader_demo read-positions``
- ``python3 -m ctrader_demo amend-sl --position-id ID --stop-loss PRICE --take-profit PRICE``
"""

from __future__ import annotations

__version__ = "0.1.0"


def read_positions(*, transport_factory=None, urlopen=None) -> dict:
    """Read open positions and floating P&L. Returns ``{code, message, ...}``."""

    from ctrader_demo.cli import execute

    kwargs = {}
    if transport_factory is not None:
        kwargs["transport_factory"] = transport_factory
    if urlopen is not None:
        kwargs["urlopen"] = urlopen
    return execute(["read-positions"], **kwargs)


def amend_sltp(
    position_id: int,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    *,
    transport_factory=None,
    urlopen=None,
) -> dict:
    """Amend stop loss / take profit. Returns ``{code, message, ...}``."""

    from ctrader_demo.cli import execute

    argv = ["amend-sl", "--position-id", str(position_id)]
    if stop_loss is not None:
        argv.extend(["--stop-loss", str(stop_loss)])
    if take_profit is not None:
        argv.extend(["--take-profit", str(take_profit)])
    kwargs = {}
    if transport_factory is not None:
        kwargs["transport_factory"] = transport_factory
    if urlopen is not None:
        kwargs["urlopen"] = urlopen
    return execute(argv, **kwargs)
