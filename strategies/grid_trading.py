#!/usr/bin/env python3
"""Simple grid trading simulator (teaching example, zero deps)."""

import math
import random


def simulate_prices(n=400, start=100.0, vol=0.012):
    random.seed(3)
    price = start
    out = []
    for _ in range(n):
        price *= 1.0 + vol * random.gauss(0, 1)
        out.append(price)
    return out


def run():
    prices = simulate_prices()
    lo, hi = 90.0, 110.0
    n_grids = 8
    step = (hi - lo) / n_grids
    base = 100.0
    qty = 10  # shares per grid cell

    levels = [lo + i * step for i in range(n_grids + 1)]
    buys = {}  # price level -> cost basis
    cash = 10000.0
    value = cash

    for price in prices:
        # buy one rung below the current level, sell one rung above
        idx = min(range(len(levels)), key=lambda i: abs(levels[i] - price))
        buy_at = levels[idx - 1] if idx > 0 else None
        sell_at = levels[idx + 1] if idx < len(levels) - 1 else None

        if buy_at and price <= buy_at and cash >= buy_at * qty:
            cash -= buy_at * qty
            buys[buy_at] = buys.get(buy_at, 0) + qty
        if sell_at and price >= sell_at and buys.get(sell_at, 0) > 0:
            cash += sell_at * qty
            buys[sell_at] -= qty

    shares = 0
    for k, v in buys.items():
        shares += v
    final_value = cash + shares * prices[-1]
    print(f"grid range {lo}-{hi}, {n_grids} cells, {qty} shares/cell")
    print(f"cash: {cash:.2f}, held shares: {shares}")
    print(f"final portfolio value: {final_value:.2f}")
    print(f"profit vs initial cash: {final_value - 10000:.2f}")


if __name__ == "__main__":
    run()
