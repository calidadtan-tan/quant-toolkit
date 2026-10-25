#!/usr/bin/env python3
"""RSI mean-reversion strategy (teaching example, zero deps)."""

import random


def simulate_prices(n=300, start=100.0, vol=0.015):
    random.seed(5)
    price = start
    out = []
    for _ in range(n):
        price *= 1.0 + vol * random.gauss(0, 1)
        out.append(price)
    return out


def rsi(prices, period=14):
    """Wilder's RSI."""
    if len(prices) < period + 1:
        return []
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    values = [None] * period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else float("inf")
        values.append(100.0 - 100.0 / (1.0 + rs))
    return values


def run():
    prices = simulate_prices()
    sig = rsi(prices, 14)
    position = 0
    entry = None
    equity = 1.0
    trades = 0

    for i in range(14, len(prices)):
        if position == 0 and sig[i] is not None and sig[i] < 30:
            position = 1
            entry = prices[i]
            trades += 1
            print(f"day {i}: BUY  at {prices[i]:.2f} (RSI {sig[i]:.1f})")
        elif position == 1 and sig[i] is not None and sig[i] > 70:
            position = 0
            equity *= prices[i] / entry
            print(f"day {i}: SELL at {prices[i]:.2f} (RSI {sig[i]:.1f})")

    if position == 1:
        equity *= prices[-1] / entry
    buy_hold = prices[-1] / prices[0]
    print(f"\nstrategy equity: {equity:.3f}  ({100 * (equity - 1):.1f}%)")
    print(f"buy-and-hold:    {buy_hold:.3f}  ({100 * (buy_hold - 1):.1f}%)")
    print(f"trades: {trades}")


if __name__ == "__main__":
    run()
