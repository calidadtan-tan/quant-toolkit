"""Executable spec for the pure rules in Include/S01Common.mqh.

The Expert Advisor cannot be compiled here (no MetaEditor). These tests
lock the ladder, risk cap, lot floor, sessions, and profile table so the
MQL5 stays aligned with Strategy-01 DEMO.
"""

from __future__ import annotations

import math
import pathlib
import re
import unittest
from datetime import datetime, timedelta


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMON = ROOT / "Include" / "S01Common.mqh"
ENGINE = ROOT / "Include" / "S01Engine.mqh"
EA = ROOT / "Strategy01Demo.mq5"


def highest_rung(peak: float, first: float, step: float) -> float:
    if first <= 0.0 or step <= 0.0:
        return 0.0
    if peak + 1e-9 < first:
        return 0.0
    k = math.floor((peak - first) / step + 1e-12)
    if k < 0.0:
        k = 0.0
    return first + k * step


def usd_lock_price(direction: int, entry: float, money_per_unit: float,
                   rung: float, lock_back: float, extra_cost: float) -> float:
    if direction == 0 or entry <= 0.0 or money_per_unit <= 0.0 or rung <= 0.0:
        return 0.0
    need = rung - lock_back + extra_cost
    if need < 0.0:
        need = 0.0
    sl = entry + need / money_per_unit if direction > 0 else entry - need / money_per_unit
    if sl <= 0.0:
        return 0.0
    return sl


def risk_fraction(profile_risk: float, kelly_sim: float, f_star: float,
                  global_cap: float, input_frac: float) -> float:
    cap = 0.01
    if global_cap > 0.0 and global_cap < cap:
        cap = global_cap
    quarter_f = 0.25 * f_star
    if quarter_f > 0.0 and quarter_f < cap:
        cap = quarter_f
    if input_frac > 0.0 and input_frac < cap:
        cap = input_frac
    frac = profile_risk
    if frac > cap:
        frac = cap
    if frac < 0.0:
        frac = 0.0
    if kelly_sim > 0.0:
        qk = 0.25 * kelly_sim
        if qk < frac:
            frac = qk
    return frac


def floor_lots(risk_usd: float, per_lot: float, step: float,
               min_lot: float, max_lot: float) -> float:
    if risk_usd <= 0.0 or per_lot <= 0.0 or step <= 0.0:
        return 0.0
    steps_d = risk_usd / per_lot / step
    steps = math.floor(steps_d + 1e-8)
    cap = 0
    if max_lot > 0.0:
        cap = math.floor(max_lot / step + 1e-8)
    if steps < 0:
        steps = 0
    if (steps + 1.0) * step * per_lot <= risk_usd + 1e-6:
        if cap <= 0 or steps + 1 <= cap:
            steps += 1
    while steps > 0 and steps * step * per_lot > risk_usd + 1e-6:
        steps -= 1
    if cap > 0 and steps > cap:
        steps = cap
    while steps > 0 and steps * step * per_lot > risk_usd + 1e-6:
        steps -= 1
    if steps < 1:
        return 0.0
    lots = float(steps) * step
    if lots + 1e-10 < min_lot:
        return 0.0
    return lots


def structure_dist(direction: int, entry: float, swing_low: float, swing_high: float,
                   atr: float, atr_mult: float, swing_buffer: float) -> float:
    if entry <= 0.0 or atr <= 0.0 or atr_mult <= 0.0:
        return 0.0
    if direction > 0:
        sl = max(swing_low - swing_buffer * atr, entry - atr_mult * atr)
        dist = entry - sl
        if dist <= 0.0:
            dist = atr_mult * atr
        return dist
    if direction < 0:
        sl = min(swing_high + swing_buffer * atr, entry + atr_mult * atr)
        dist = sl - entry
        if dist <= 0.0:
            dist = atr_mult * atr
        return dist
    return 0.0


def apply_floors(structure: float, min_sl_price: float, atr_m30: float, atr_mult: float) -> float:
    dist = structure
    if dist < 0.0:
        dist = 0.0
    if min_sl_price > dist:
        dist = min_sl_price
    if atr_m30 > 0.0 and atr_mult > 0.0:
        floor_dist = atr_mult * atr_m30
        if floor_dist > dist:
            dist = floor_dist
    return dist


def regime_dir(ema50: float, ema200: float, atr: float, close: float,
               median_atr: float, gap_mult: float, boom_mult: float) -> int:
    if atr <= 0.0 or ema50 <= 0.0 or ema200 <= 0.0 or close <= 0.0:
        return 0
    if abs(ema50 - ema200) < gap_mult * atr:
        return 0
    if median_atr > 0.0 and boom_mult > 0.0 and atr > median_atr * boom_mult:
        return 0
    if ema50 > ema200 and close > ema50:
        return 1
    if ema50 < ema200 and close < ema50:
        return -1
    return 0


def session_bucket(mins: int) -> str:
    if 7 * 60 <= mins < 15 * 60:
        return "asia"
    if 15 * 60 <= mins < 21 * 60:
        return "london"
    return "ny"


def in_us_cash(mins: int) -> bool:
    return mins >= 22 * 60 + 30 or mins < 5 * 60


def in_tokyo(mins: int) -> bool:
    return 8 * 60 <= mins < 14 * 60


def tighter_stop(direction: int, a: float, b: float) -> float:
    ha = a > 0.0
    hb = b > 0.0
    if not ha and not hb:
        return 0.0
    if ha and not hb:
        return a
    if hb and not ha:
        return b
    return max(a, b) if direction > 0 else min(a, b)


def mql_dow(dt: datetime) -> int:
    return (dt.weekday() + 1) % 7


def week_start_hkt(dt: datetime) -> datetime:
    dow = mql_dow(dt)
    since = 6 if dow == 0 else dow - 1
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=since)


class RuleTests(unittest.TestCase):
    def test_rung_ladder_starts_at_50_then_steps_100(self):
        self.assertEqual(highest_rung(49.99, 50, 100), 0)
        self.assertEqual(highest_rung(50, 50, 100), 50)
        self.assertEqual(highest_rung(149.9, 50, 100), 50)
        self.assertEqual(highest_rung(150, 50, 100), 150)
        self.assertEqual(highest_rung(1000, 50, 100), 950)
        # Older handoff ladder is the same function with a later first rung.
        self.assertEqual(highest_rung(100, 100, 100), 100)
        self.assertEqual(highest_rung(250, 100, 100), 200)

    def test_lock_price_keeps_rung_minus_30_plus_cost(self):
        sl = usd_lock_price(1, 1.1000, 100000.0, 50, 30, 7.0)
        self.assertAlmostEqual(sl, 1.1000 + 27.0 / 100000.0)
        short = usd_lock_price(-1, 150.0, 1.0, 150, 30, 0.0)
        self.assertAlmostEqual(short, 150.0 - 120.0)

    def test_risk_cap_uses_profile_quarter_kelly_and_one_percent(self):
        eur = risk_fraction(0.006, 0.090, 0.126, 0.01, 0.01)
        self.assertAlmostEqual(eur, 0.006)
        jpy = risk_fraction(0.005, -0.054, 0.126, 0.01, 0.01)
        self.assertAlmostEqual(jpy, 0.005)
        tightened = risk_fraction(0.006, 0.090, 0.126, 0.02, 0.004)
        self.assertAlmostEqual(tightened, 0.004)
        tiny_f = risk_fraction(0.008, 0.123, 0.02, 0.01, 0.01)
        self.assertAlmostEqual(tiny_f, 0.005)

    def test_lot_floor_never_exceeds_risk(self):
        lots = floor_lots(100, 30, 0.01, 0.01, 100)
        self.assertAlmostEqual(lots, 3.33)
        self.assertLessEqual(lots * 30, 100 + 1e-6)
        exact = floor_lots(100, 40, 0.01, 0.01, 100)
        self.assertAlmostEqual(exact, 2.5)
        self.assertEqual(floor_lots(50, 6000, 0.01, 0.01, 100), 0.0)
        self.assertEqual(floor_lots(100, 30, 0.01, 5.0, 100), 0.0)
        capped = floor_lots(10_000, 10, 0.01, 0.01, 1.0)
        self.assertAlmostEqual(capped, 1.0)

    def test_structure_then_e_f_floors(self):
        near = structure_dist(1, 100, 99, 110, 2, 1.5, 0.1)
        self.assertAlmostEqual(near, 1.2)
        far = structure_dist(1, 100, 90, 110, 2, 1.5, 0.1)
        self.assertAlmostEqual(far, 3.0)
        widened = apply_floors(far, 8 * 0.0001, 10, 1.5)
        self.assertAlmostEqual(widened, 15.0)
        eur = apply_floors(0.0005, 8 * 0.0001, 0.0010, 2.0)
        self.assertAlmostEqual(eur, 0.0020)

    def test_regime_off_conditions(self):
        self.assertEqual(regime_dir(2, 1, 1, 2.5, 1, 0.15, 2.2), 1)
        self.assertEqual(regime_dir(2, 1, 1, 1.5, 1, 0.15, 2.2), 0)
        self.assertEqual(regime_dir(1.1, 1.0, 1, 1.2, 1, 0.15, 2.2), 0)
        self.assertEqual(regime_dir(2, 1, 3, 2.5, 1, 0.15, 2.2), 0)
        self.assertEqual(regime_dir(1, 2, 1, 0.5, 1, 0.15, 2.2), -1)

    def test_sessions(self):
        self.assertEqual(session_bucket(7 * 60), "asia")
        self.assertEqual(session_bucket(15 * 60 - 1), "asia")
        self.assertEqual(session_bucket(15 * 60), "london")
        self.assertEqual(session_bucket(21 * 60 - 1), "london")
        self.assertEqual(session_bucket(21 * 60), "ny")
        self.assertEqual(session_bucket(6 * 60 + 59), "ny")
        self.assertTrue(in_us_cash(22 * 60 + 30))
        self.assertTrue(in_us_cash(4 * 60 + 59))
        self.assertFalse(in_us_cash(5 * 60))
        self.assertFalse(in_us_cash(22 * 60 + 29))
        self.assertTrue(in_tokyo(8 * 60))
        self.assertTrue(in_tokyo(13 * 60 + 59))
        self.assertFalse(in_tokyo(14 * 60))
        self.assertFalse(in_tokyo(7 * 60 + 59))

    def test_tighter_stop_never_picks_the_looser_one(self):
        self.assertEqual(tighter_stop(1, 1.12, 1.15), 1.15)
        self.assertEqual(tighter_stop(-1, 1.08, 1.05), 1.05)
        self.assertEqual(tighter_stop(1, 1.12, 0.0), 1.12)
        self.assertEqual(tighter_stop(1, 0.0, 0.0), 0.0)

    def test_hkt_week_starts_monday(self):
        thursday = datetime(2026, 11, 5, 18, 30)
        self.assertEqual(week_start_hkt(thursday), datetime(2026, 11, 2))
        sunday = datetime(2026, 11, 8, 9, 0)
        self.assertEqual(week_start_hkt(sunday), datetime(2026, 11, 2))
        monday = datetime(2026, 11, 2, 15, 0)
        self.assertEqual(week_start_hkt(monday), datetime(2026, 11, 2))

    def test_profiles_match_the_pack(self):
        text = COMMON.read_text(encoding="utf-8")
        pat = re.compile(
            r'S01Fill\(\s*(\d+),\s*"([^"]+)",\s*"([^"]+)",\s*'
            r'([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?),\s*'
            r'([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?),\s*'
            r'(\d+),\s*(\d+),\s*(\d+),\s*([+-]?\d+(?:\.\d+)?),\s*(true|false)'
        )
        found = pat.findall(text)
        expected = [
            ("0", "USDJPY", "trend_pullback", "0.01", "12.0", "0.8", "-0.054", "0.005", "45", "3", "5", "0.6", "true"),
            ("1", "EURUSD", "trend_pullback", "0.0001", "8.0", "0.8", "0.090", "0.006", "60", "3", "5", "0.6", "true"),
            ("2", "USDCAD", "mean_revert_fade", "0.0001", "10.0", "0.8", "-0.595", "0.0025", "60", "3", "10", "0.4", "true"),
            ("3", "XAUUSD", "trend_pullback", "0.01", "300.0", "30.0", "0.039", "0.006", "45", "2", "5", "0.7", "true"),
            ("4", "NAS100", "breakout_momentum", "1.0", "40.0", "4.0", "-0.025", "0.004", "30", "2", "5", "0.7", "false"),
            ("5", "US500", "trend_pullback", "1.0", "8.0", "0.8", "0.036", "0.005", "30", "2", "5", "0.6", "false"),
            ("6", "JPN225", "trend_pullback", "1.0", "120.0", "10.0", "0.123", "0.008", "30", "2", "5", "0.6", "false"),
            ("7", "BTCUSD", "trend_pullback", "1.0", "200.0", "30.0", "0.069", "0.006", "60", "5", "15", "0.7", "false"),
        ]
        self.assertEqual(found, expected)
        self.assertIn("S01Trail4(1, 0.5, 0.9, 1.0, 0.7, 2.0, 0.5, 3.0, 0.35);", text)
        self.assertIn("S01_HARD_BTC", text)
        self.assertIn("S01_HARD_US", text)
        self.assertIn("S01_HARD_TKY", text)

    def test_sources_have_no_secrets_and_balance(self):
        for path in (COMMON, ENGINE, EA):
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            lowered = text.lower()
            for banned in ("access_token", "client_secret", "refresh_token", "api_key", "ctrader_client"):
                self.assertNotIn(banned, lowered)
            self.assertTrue(_balanced(text), path.name)
        engine = ENGINE.read_text(encoding="utf-8")
        self.assertTrue(engine.isascii())
        common = COMMON.read_text(encoding="utf-8")
        self.assertTrue(common.isascii())
        ea = EA.read_bytes()
        self.assertTrue(ea.startswith(b"\xef\xbb\xbf"), "mq5 should carry a UTF-8 BOM for MetaEditor")


def _balanced(text: str) -> bool:
    stripped = _strip_mql(text)
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in stripped:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
    return not stack


def _strip_mql(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if text[i] == '"':
            i += 1
            while i < n:
                if text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if text[i] == "'":
            i += 1
            while i < n and text[i] != "'":
                if text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


if __name__ == "__main__":
    unittest.main()
