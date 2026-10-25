#!/usr/bin/env python3
"""Cross-sectional momentum rotation (teaching example, zero deps)."""

import random


def simulate_assets(n_assets=4, n_days=250, start=100.0):
    """Generate independent random-walk price series per asset."""
    assets = {}
    for a in range(n_assets):
        price = start
        series = []
        for _ in range(n_days):
            price *= 1.0 + 0.0004 + 0.02 * random.gauss(0, 1)
            series.append(price)
        assets[f"asset_{a}"] = series
    return assets


def returns_1d(series):
    return [series[i] / series[i - 1] - 1.0 for i in range(1, len(series))]


def run():
    random.seed(11)
    assets = simulate_assets()
    lookback = 20
    rebalance = 10  # rebalance every 10 days

    # monthly momentum: cumulative return over the lookback window
    momentum = {}
    for name, series in assets.items():
        ret = returns_1d(series)
        momentum[name] = 1.0
        for r in ret[-lookback:]:
            momentum[name] *= 1.0 + r

    ranked = sorted(momentum.items(), key=lambda kv: kv[1], reverse=True)
    print("momentum ranking (last %d days):" % lookback)
    for name, m in ranked:
        print(f"  {name}: {100 * (m - 1):+.1f}%")

    winner = ranked[0][0]
    hold_ret = 1.0
    for i in range(lookback, len(assets[winner])):
        if i % rebalance == 0:
            hold_ret *= 1.0 + returns_1d(assets[winner])[i - 1]

    avg = 1.0
    for name in assets:
        avg *= 1.0 + sum(returns_1d(assets[name])) / len(assets[name])
    avg = (avg ** (1.0 / len(assets))) - 1.0

    print(f"\nwinner {winner} held on: {100 * (hold_ret - 1):+.1f}%")
    print(f"equal-weight average per asset: {100 * avg:+.1f}%")


if __name__ == "__main__":
    run()
