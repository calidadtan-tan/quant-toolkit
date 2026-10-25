#!/usr/bin/env python3
"""Dual moving average crossover strategy (teaching example, zero deps)."""

import random


def simulate_prices(n=300, start=100.0, drift=0.0003, vol=0.015):
    """Generate a simple random-walk price series."""
    prices = []
    price = start
    for _ in range(n):
        price *= 1.0 + drift + vol * random.gauss(0, 1)
        prices.append(price)
    return prices


def sma(values, window):
    """Simple moving average, None where there is not enough data."""
    out = [None] * len(values)
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= window:
            acc -= values[i - window]
        if i >= window - 1:
            out[i] = acc / window
    return out


def run():
    random.seed(7)
    prices = simulate_prices()
    fast = sma(prices, 20)
    slow = sma(prices, 50)

    position = 0  # 0 = cash, 1 = holding
    equity = 1.0
    entry = None
    trades = 0

    for i in range(1, len(prices)):
        if fast[i] is None or slow[i] is None:
            continue
        if position == 0 and fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]:
            position = 1
            entry = prices[i]
            trades += 1
            print(f"day {i}: BUY  at {prices[i]:.2f}")
        elif position == 1 and fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]:
            position = 0
            equity *= prices[i] / entry
            print(f"day {i}: SELL at {prices[i]:.2f}")

    if position == 1:
        equity *= prices[-1] / entry

    buy_hold = prices[-1] / prices[0]
    print(f"\nstrategy equity: {equity:.3f}  ({100 * (equity - 1):.1f}%)")
    print(f"buy-and-hold:    {buy_hold:.3f}  ({100 * (buy_hold - 1):.1f}%)")
    print(f"trades: {trades}")


if __name__ == "__main__":
    run()
