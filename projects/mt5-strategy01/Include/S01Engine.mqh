//+------------------------------------------------------------------+
//| S01Engine.mqh                                                    |
//| M30+M15 regime, M5 pullback, squeeze/chop, sized hard stop.     |
//| Include this file AFTER the EA input declarations.              |
//+------------------------------------------------------------------+
#ifndef S01_ENGINE_MQH
#define S01_ENGINE_MQH

#include "S01Common.mqh"

//+------------------------------------------------------------------+
bool S01ClosedValue(const int handle, double &value)
  {
   value = 0.0;
   if(handle == INVALID_HANDLE)
      return(false);
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, 0, 2, buf) != 2)
      return(false);
   value = buf[1];
   if(value <= 0.0 || value == EMPTY_VALUE)
      return(false);
   return(true);
  }

//+------------------------------------------------------------------+
bool S01ClosedWindow(const int handle, const int closed_count, double &out[])
  {
   if(handle == INVALID_HANDLE || closed_count < 5)
      return(false);
   ArrayResize(out, closed_count);
   ArraySetAsSeries(out, false);
   double buf[];
   ArraySetAsSeries(buf, true);
   int need = closed_count + 1;
   if(CopyBuffer(handle, 0, 0, need, buf) != need)
      return(false);
   for(int i = 0; i < closed_count; i++)
     {
      out[i] = buf[i + 1];
      if(out[i] <= 0.0 || out[i] == EMPTY_VALUE)
         return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
double S01NormPct(const double raw)
  {
   double pct = raw;
   if(pct > 1.0 && pct <= 100.0)
      pct = pct / 100.0;
   if(pct < 0.0)
      pct = 0.0;
   if(pct > 1.0)
      pct = 1.0;
   return(pct);
  }

//+------------------------------------------------------------------+
double S01KeepFrac()
  {
   double keep = InpSlKeepFrac;
   if(keep > 1.0 && keep <= 100.0)
      keep = keep / 100.0;
   if(keep < 0.0)
      keep = 0.0;
   if(keep > 1.0)
      keep = 1.0;
   return(keep);
  }

//+------------------------------------------------------------------+
bool S01MarketReady(const S01Sym &sx)
  {
   if(!sx.active || StringLen(sx.symbol) == 0)
      return(false);
   int need_m5 = InpPullbackBars + InpExpandBars + 5;
   if(need_m5 < 40)
      need_m5 = 40;
   if(Bars(sx.symbol, PERIOD_M30) < 220)
      return(false);
   if(Bars(sx.symbol, PERIOD_M15) < 220)
      return(false);
   if(Bars(sx.symbol, PERIOD_M5) < need_m5)
      return(false);
   if(!SeriesInfoInteger(sx.symbol, PERIOD_M30, SERIES_SYNCHRONIZED))
      return(false);
   if(!SeriesInfoInteger(sx.symbol, PERIOD_M15, SERIES_SYNCHRONIZED))
      return(false);
   if(!SeriesInfoInteger(sx.symbol, PERIOD_M5, SERIES_SYNCHRONIZED))
      return(false);
   if(BarsCalculated(sx.h_m30_ema200) < 210)
      return(false);
   if(BarsCalculated(sx.h_m30_atr) < InpAtrStatsBars + 2)
      return(false);
   if(BarsCalculated(sx.h_m15_ema200) < 210)
      return(false);
   if(BarsCalculated(sx.h_m15_atr) < InpAtrStatsBars + 2)
      return(false);
   if(BarsCalculated(sx.h_m5_ema20) < 25)
      return(false);
   if(BarsCalculated(sx.h_m5_atr) < 20)
      return(false);
   return(true);
  }

//+------------------------------------------------------------------+
bool S01SideTradable(const string symbol, const int dir)
  {
   long mode = SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
   if(mode == SYMBOL_TRADE_MODE_DISABLED || mode == SYMBOL_TRADE_MODE_CLOSEONLY)
      return(false);
   if(dir > 0 && mode == SYMBOL_TRADE_MODE_SHORTONLY)
      return(false);
   if(dir < 0 && mode == SYMBOL_TRADE_MODE_LONGONLY)
      return(false);
   return(true);
  }

//+------------------------------------------------------------------+
// Closed M5 rates[] is a timeseries: index 1 is the last closed bar.
// Clear pullback = a bar overlaps M30 EMA20, or a newer bar wicks into
// the 38.2-61.8 zone of the lookback impulse. This is the MQL5 stand-in
// for the Python signal engine's EMA/fib touch.
bool S01Pullback(const int dir, MqlRates &rates[], const int copied,
                 const double ema_ht, const double atr_m5,
                 bool &clear_pb, bool &near_zone,
                 double &swing_low, double &swing_high)
  {
   clear_pb = false;
   near_zone = false;
   swing_low = 0.0;
   swing_high = 0.0;
   int n = InpPullbackBars;
   if(n > copied - 1)
      n = copied - 1;
   if(n < 5 || atr_m5 <= 0.0 || ema_ht <= 0.0)
      return(false);

   swing_low = rates[1].low;
   swing_high = rates[1].high;
   for(int k = 2; k <= n; k++)
     {
      if(rates[k].low < swing_low)
         swing_low = rates[k].low;
      if(rates[k].high > swing_high)
         swing_high = rates[k].high;
     }

   double band = 0.05 * atr_m5;
   bool overlap = false;
   bool traded_above = false;
   bool traded_below = false;
   for(int k = 1; k <= n; k++)
     {
      if(rates[k].low <= ema_ht + band && rates[k].high >= ema_ht - band)
         overlap = true;
      if(rates[k].high > ema_ht)
         traded_above = true;
      if(rates[k].low < ema_ht)
         traded_below = true;
     }
   bool ema_touch = false;
   if(dir > 0)
      ema_touch = (overlap && traded_above);
   else if(dir < 0)
      ema_touch = (overlap && traded_below);

   bool fib_touch = false;
   int idx_ext = 1;
   if(dir > 0)
     {
      for(int k = 2; k <= n; k++)
        {
         if(rates[k].high > rates[idx_ext].high)
            idx_ext = k;
        }
      double base = rates[idx_ext].low;
      for(int k = idx_ext; k <= n; k++)
        {
         if(rates[k].low < base)
            base = rates[k].low;
        }
      double span = rates[idx_ext].high - base;
      if(span >= 0.5 * atr_m5)
        {
         double fib_top = rates[idx_ext].high - 0.382 * span;
         double fib_bot = rates[idx_ext].high - 0.618 * span;
         for(int k = 1; k < idx_ext; k++)
           {
            if(rates[k].low <= fib_top && rates[k].low >= fib_bot - band)
               fib_touch = true;
           }
        }
     }
   else if(dir < 0)
     {
      for(int k = 2; k <= n; k++)
        {
         if(rates[k].low < rates[idx_ext].low)
            idx_ext = k;
        }
      double base = rates[idx_ext].high;
      for(int k = idx_ext; k <= n; k++)
        {
         if(rates[k].high > base)
            base = rates[k].high;
        }
      double span = base - rates[idx_ext].low;
      if(span >= 0.5 * atr_m5)
        {
         double fib_bot = rates[idx_ext].low + 0.382 * span;
         double fib_top = rates[idx_ext].low + 0.618 * span;
         for(int k = 1; k < idx_ext; k++)
           {
            if(rates[k].high >= fib_bot && rates[k].high <= fib_top + band)
               fib_touch = true;
           }
        }
     }

   clear_pb = (ema_touch || fib_touch);
   if(InpNearZoneAtr > 0.0 && MathAbs(rates[1].close - ema_ht) <= InpNearZoneAtr * atr_m5)
      near_zone = true;
   return(true);
  }

//+------------------------------------------------------------------+
bool S01Expanded(const int dir, MqlRates &rates[], const int copied)
  {
   int n_bars = InpExpandBars;
   if(copied < n_bars + 2)
      return(false);
   double hh = rates[2].high;
   double ll = rates[2].low;
   for(int k = 3; k <= n_bars + 1; k++)
     {
      if(rates[k].high > hh)
         hh = rates[k].high;
      if(rates[k].low < ll)
         ll = rates[k].low;
     }
   if(dir > 0)
      return(rates[1].close > hh);
   if(dir < 0)
      return(rates[1].close < ll);
   return(false);
  }

//+------------------------------------------------------------------+
double S01TickSize(const string symbol)
  {
   double tick = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(tick <= 0.0)
      tick = 0.00001;
   return(tick);
  }

//+------------------------------------------------------------------+
// dir > 0 ceils (tighter long stop). dir < 0 floors (tighter short stop).
double S01AlignStop(const int dir, const string symbol, const double price)
  {
   double tick = S01TickSize(symbol);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double steps;
   if(dir > 0)
      steps = MathCeil(price / tick - 1e-10);
   else
      steps = MathFloor(price / tick + 1e-10);
   return(NormalizeDouble(steps * tick, digits));
  }

//+------------------------------------------------------------------+
double S01AlignWider(const int dir, const string symbol, const double price)
  {
   if(dir > 0)
      return(S01AlignStop(-1, symbol, price));
   return(S01AlignStop(1, symbol, price));
  }

//+------------------------------------------------------------------+
double S01MoneyPerUnit(const string symbol, const int dir,
                       const double volume, const double entry)
  {
   if(volume <= 0.0 || entry <= 0.0)
      return(0.0);
   double move = S01TickSize(symbol) * 100.0;
   if(move <= 0.0)
      return(0.0);
   double exit_px = (dir > 0) ? entry + move : entry - move;
   if(exit_px <= 0.0)
      return(0.0);
   double money = 0.0;
   ENUM_ORDER_TYPE kind = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcProfit(kind, symbol, volume, entry, exit_px, money))
      return(0.0);
   if(money <= 0.0)
      return(0.0);
   return(money / move);
  }

//+------------------------------------------------------------------+
void S01Block(S01Plan &plan, const int dir, const string reason)
  {
   plan.dir = dir;
   plan.tradable = false;
   plan.lots = 0.0;
   plan.sl = 0.0;
   plan.tp = 0.0;
   plan.r_dist = 0.0;
   plan.reason = reason;
  }

//+------------------------------------------------------------------+
void S01BuildOrder(const string symbol, const int dir, const S01Profile &p,
                   const double signal_close, const double live_entry,
                   const double swing_low, const double swing_high,
                   const double atr_m5, const double atr_m30, S01Plan &plan)
  {
   double floor_mult = (p.key == "EURUSD") ? InpAtrFloorF : InpAtrFloorE;
   double min_sl_px = p.min_sl_pips * p.pip;
   double sig_raw = S01StructureDist(dir, signal_close, swing_low, swing_high,
                                     atr_m5, InpStructureAtrMult, InpSwingBufferAtr);
   double live_raw = S01StructureDist(dir, live_entry, swing_low, swing_high,
                                      atr_m5, InpStructureAtrMult, InpSwingBufferAtr);
   double sig = S01ApplyFloors(sig_raw, min_sl_px, atr_m30, floor_mult);
   double dist = S01ApplyFloors(live_raw, min_sl_px, atr_m30, floor_mult);
   double keep = S01KeepFrac();
   if(keep > 0.0 && sig > 0.0 && dist < keep * sig)
      dist = keep * sig;

   if(atr_m5 > 0.0 && InpSlAbandonAtr > 0.0 && dist < InpSlAbandonAtr * atr_m5)
     {
      S01Block(plan, dir, "SL_TOO_TIGHT");
      return;
     }

   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int stops = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double broker = ((double)stops + 1.0) * point;
   if(broker < point)
      broker = point;
   if(dist < broker)
      dist = broker;
   if(dist <= 0.0)
     {
      S01Block(plan, dir, "SL_TOO_TIGHT");
      return;
     }

   if(InpDriftVsSl > 0.0 && MathAbs(live_entry - signal_close) > InpDriftVsSl * dist)
     {
      S01Block(plan, dir, "PRICE_DRIFT");
      return;
     }

   double sl = (dir > 0) ? live_entry - dist : live_entry + dist;
   sl = S01AlignWider(dir, symbol, sl);
   dist = MathAbs(live_entry - sl);
   if(dir > 0 && !(sl < live_entry))
     {
      S01Block(plan, dir, "SL_TOO_TIGHT");
      return;
     }
   if(dir < 0 && !(sl > live_entry))
     {
      S01Block(plan, dir, "SL_TOO_TIGHT");
      return;
     }
   if(dist < broker)
     {
      if(dir > 0)
         sl = S01AlignWider(dir, symbol, live_entry - broker);
      else
         sl = S01AlignWider(dir, symbol, live_entry + broker);
      dist = MathAbs(live_entry - sl);
     }

   double slip = p.slip_pips * p.pip;
   double exit_px = (dir > 0) ? live_entry - (dist + slip) : live_entry + (dist + slip);
   double loss = 0.0;
   ENUM_ORDER_TYPE kind = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(exit_px <= 0.0 || !OrderCalcProfit(kind, symbol, 1.0, live_entry, exit_px, loss))
     {
      S01Block(plan, dir, "NO_DATA");
      return;
     }
   double per_lot = -loss;
   if(per_lot <= 0.0)
     {
      S01Block(plan, dir, "LOTS_ZERO");
      return;
     }
   if(p.comm_on)
      per_lot += InpCommissionBufferUsd;

   double basis = InpUseBalance ? AccountInfoDouble(ACCOUNT_BALANCE)
                                : AccountInfoDouble(ACCOUNT_EQUITY);
   double frac = S01RiskFraction(p.risk_frac, p.kelly_sim, InpFStar,
                                 InpGlobalRiskCap, InpRiskFrac);
   double risk_usd = frac * basis;

   double sym_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(sym_step <= 0.0)
      sym_step = InpLotStep;
   double step = sym_step;
   if(InpLotStep > sym_step)
     {
      double multiples = MathFloor(InpLotStep / sym_step + 1e-8);
      if(multiples < 1.0)
         multiples = 1.0;
      step = multiples * sym_step;
     }
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   if(InpMinLot > min_lot)
      min_lot = InpMinLot;
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lots = S01FloorLots(risk_usd, per_lot, step, min_lot, max_lot);
   if(lots <= 0.0)
     {
      S01Block(plan, dir, "LOTS_ZERO");
      return;
     }

   double tp = 0.0;
   if(InpUseFarTp && InpFarTpR > 0.0)
     {
      tp = (dir > 0) ? live_entry + InpFarTpR * dist : live_entry - InpFarTpR * dist;
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double tick = S01TickSize(symbol);
      tp = NormalizeDouble(MathRound(tp / tick) * tick, digits);
      if(MathAbs(tp - live_entry) < broker)
         tp = 0.0;
      if(dir > 0 && tp <= live_entry)
         tp = 0.0;
      if(dir < 0 && tp >= live_entry)
         tp = 0.0;
     }

   string tag = "OPEN";
   if(plan.cautious && plan.soft_chase)
      tag = "OPEN_CAUTIOUS_CHASE_SOFT";
   else if(plan.cautious)
      tag = "OPEN_CAUTIOUS";
   else if(plan.soft_chase)
      tag = "OPEN_CHASE_SOFT";

   plan.dir = dir;
   plan.lots = lots;
   plan.sl = sl;
   plan.tp = tp;
   plan.r_dist = dist;
   plan.reason = tag;
   plan.tradable = true;
  }

//+------------------------------------------------------------------+
void S01Decide(S01Sym &sx, const bool week_kill, const bool in_cooldown,
               const bool has_position, S01Plan &plan)
  {
   S01PlanReset(plan);
   if(!sx.active || sx.profile < 0 || sx.profile >= S01_COUNT)
     {
      plan.reason = "NO_DATA";
      return;
     }
   if(week_kill)
     {
      plan.reason = "WEEKLY_KILL";
      return;
     }

   bool cautious = false;
   string sess = S01SessionReason(g_s01_profiles[sx.profile], S01NowHkt(), cautious);
   if(StringLen(sess) > 0)
     {
      plan.reason = sess;
      return;
     }

   if(!S01MarketReady(sx))
     {
      plan.reason = "NO_DATA";
      return;
     }

   double ema50 = 0.0, ema200 = 0.0, atr = 0.0, ema20 = 0.0;
   double m15_ema50 = 0.0, m15_ema200 = 0.0, m15_atr = 0.0;
   double m5_ema20 = 0.0, m5_atr = 0.0;
   if(!S01ClosedValue(sx.h_m30_ema50, ema50) ||
      !S01ClosedValue(sx.h_m30_ema200, ema200) ||
      !S01ClosedValue(sx.h_m30_ema20, ema20) ||
      !S01ClosedValue(sx.h_m30_atr, atr) ||
      !S01ClosedValue(sx.h_m15_ema50, m15_ema50) ||
      !S01ClosedValue(sx.h_m15_ema200, m15_ema200) ||
      !S01ClosedValue(sx.h_m15_atr, m15_atr) ||
      !S01ClosedValue(sx.h_m5_ema20, m5_ema20) ||
      !S01ClosedValue(sx.h_m5_atr, m5_atr))
     {
      plan.reason = "NO_DATA";
      return;
     }

   double m30_win[];
   double m15_win[];
   if(!S01ClosedWindow(sx.h_m30_atr, InpAtrStatsBars, m30_win) ||
      !S01ClosedWindow(sx.h_m15_atr, InpAtrStatsBars, m15_win))
     {
      plan.reason = "NO_DATA";
      return;
     }
   double med30 = 0.0, p20 = 0.0, med15 = 0.0, p15 = 0.0;
   double sq_pct = S01NormPct(InpSqueezePct);
   if(!S01AtrStats(m30_win, InpAtrStatsBars, sq_pct, med30, p20) ||
      !S01AtrStats(m15_win, InpAtrStatsBars, sq_pct, med15, p15))
     {
      plan.reason = "NO_DATA";
      return;
     }

   double m30_close = iClose(sx.symbol, PERIOD_M30, 1);
   double m15_close = iClose(sx.symbol, PERIOD_M15, 1);
   if(m30_close <= 0.0 || m15_close <= 0.0)
     {
      plan.reason = "NO_DATA";
      return;
     }
   int d30 = S01RegimeDir(ema50, ema200, atr, m30_close, med30,
                          InpRegimeGapAtr, InpRegimeBoom);
   if(d30 == 0)
     {
      plan.reason = "REGIME_OFF";
      return;
     }
   int d15 = S01RegimeDir(m15_ema50, m15_ema200, m15_atr, m15_close, med15,
                          InpRegimeGapAtr, InpRegimeBoom);
   if(d15 == 0 || d15 != d30)
     {
      S01Block(plan, d30, "M15_DISAGREE");
      return;
     }

   int need = InpPullbackBars + InpExpandBars + 5;
   if(need < 40)
      need = 40;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(sx.symbol, PERIOD_M5, 0, need, rates);
   if(copied < need || copied < 12)
     {
      plan.reason = "NO_DATA";
      return;
     }

   bool clear_pb = false, near_zone = false;
   double swing_low = 0.0, swing_high = 0.0;
   if(!S01Pullback(d30, rates, copied, ema20, m5_atr, clear_pb, near_zone,
                   swing_low, swing_high))
     {
      plan.reason = "NO_DATA";
      return;
     }

   bool squeeze = (atr <= p20);
   bool expanded = S01Expanded(d30, rates, copied);
   if(squeeze && !expanded)
     {
      S01Block(plan, d30, "RANGE_SQUEEZE_NO_EXPAND");
      return;
     }

   double signal_close = rates[1].close;
   double chase = 0.0;
   if(m5_atr > 0.0)
     {
      if(d30 > 0 && signal_close > ema20)
         chase = (signal_close - ema20) / m5_atr;
      else if(d30 < 0 && signal_close < ema20)
         chase = (ema20 - signal_close) / m5_atr;
     }
   bool hard = (InpChaseHardAtr > 0.0 && chase > InpChaseHardAtr);
   bool soft = (InpChaseSoftAtr > 0.0 && chase > InpChaseSoftAtr);
   if(hard)
     {
      S01Block(plan, d30, "CHASE_BLOCKED");
      return;
     }

   bool chop = false;
   if(InpChopRatio > 0.0 && atr > 0.0 && MathAbs(ema50 - ema200) / atr < InpChopRatio)
      chop = true;
   if(chop)
     {
      if(!clear_pb || soft)
        {
         S01Block(plan, d30, "CHOP_SKIP");
         return;
        }
     }
   else if(!(squeeze && expanded))
     {
      if(!clear_pb && !near_zone)
        {
         S01Block(plan, d30, "NO_PULLBACK");
         return;
        }
     }

   bool confirm = false;
   if(d30 > 0)
      confirm = (signal_close > m5_ema20);
   else
      confirm = (signal_close < m5_ema20);
   if(!confirm)
     {
      S01Block(plan, d30, "NO_CONFIRM");
      return;
     }

   if(!S01SideTradable(sx.symbol, d30))
     {
      S01Block(plan, d30, "MARKET_CLOSED");
      return;
     }

   double live = (d30 > 0) ? SymbolInfoDouble(sx.symbol, SYMBOL_ASK)
                           : SymbolInfoDouble(sx.symbol, SYMBOL_BID);
   if(live <= 0.0)
     {
      S01Block(plan, d30, "NO_DATA");
      return;
     }

   plan.cautious = cautious;
   plan.soft_chase = soft;
   S01BuildOrder(sx.symbol, d30, g_s01_profiles[sx.profile], signal_close, live,
                 swing_low, swing_high, m5_atr, atr, plan);
   if(!plan.tradable)
      return;
   if(in_cooldown)
     {
      S01Block(plan, d30, "COOLDOWN");
      return;
     }
   if(has_position)
     {
      S01Block(plan, d30, "HAS_POSITION");
      return;
     }
  }

//+------------------------------------------------------------------+
#endif
