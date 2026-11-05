//+------------------------------------------------------------------+
//| S01Common.mqh                                                    |
//| Strategy-01 DEMO pure rules: profiles, sessions, risk, stops.   |
//| Live trading is refused by the EA. No API tokens live here.     |
//+------------------------------------------------------------------+
#ifndef S01_COMMON_MQH
#define S01_COMMON_MQH

#define S01_COUNT 8

#define S01_ASIA   1
#define S01_LONDON 2
#define S01_NY     4

#define S01_HARD_NONE 0
#define S01_HARD_US   1
#define S01_HARD_TKY  2
#define S01_HARD_BTC  3

#define S01_PREF_ANY  0
#define S01_PREF_HKFX 1
#define S01_PREF_US   2
#define S01_PREF_TKY  3

//+------------------------------------------------------------------+
struct S01Profile
  {
   string            key;
   string            style;
   double            pip;
   double            min_sl_pips;
   double            slip_pips;
   double            kelly_sim;
   double            risk_frac;
   int               cooldown_min;
   int               scan_held_min;
   int               scan_flat_min;
   double            be_at_r;
   bool              comm_on;
   int               sessions;
   int               hard_gate;
   int               preferred;
   int               trail_n;
   double            trail_at[4];
   double            trail_dist[4];
  };

struct S01Plan
  {
   int               dir;
   string            reason;
   double            lots;
   double            sl;
   double            tp;
   double            r_dist;
   bool              cautious;
   bool              soft_chase;
   bool              tradable;
  };

struct S01Sym
  {
   int               profile;
   string            symbol;
   bool              active;
   int               h_m30_ema20;
   int               h_m30_ema50;
   int               h_m30_ema200;
   int               h_m30_atr;
   int               h_m15_ema50;
   int               h_m15_ema200;
   int               h_m15_atr;
   int               h_m5_ema20;
   int               h_m5_atr;
   datetime          last_m5;
   datetime          last_eval;
   datetime          sent_bar;
   datetime          attempt_bar;
   datetime          data_retry;
   string            last_reason;
  };

S01Profile        g_s01_profiles[S01_COUNT];

//+------------------------------------------------------------------+
void S01PlanReset(S01Plan &plan)
  {
   plan.dir = 0;
   plan.reason = "";
   plan.lots = 0.0;
   plan.sl = 0.0;
   plan.tp = 0.0;
   plan.r_dist = 0.0;
   plan.cautious = false;
   plan.soft_chase = false;
   plan.tradable = false;
  }

//+------------------------------------------------------------------+
void S01Fill(const int i, const string key, const string style,
             const double pip, const double min_sl, const double slip,
             const double kelly, const double risk, const int cd,
             const int held, const int flat, const double be,
             const bool comm, const int sessions, const int hard_gate,
             const int pref)
  {
   g_s01_profiles[i].key = key;
   g_s01_profiles[i].style = style;
   g_s01_profiles[i].pip = pip;
   g_s01_profiles[i].min_sl_pips = min_sl;
   g_s01_profiles[i].slip_pips = slip;
   g_s01_profiles[i].kelly_sim = kelly;
   g_s01_profiles[i].risk_frac = risk;
   g_s01_profiles[i].cooldown_min = cd;
   g_s01_profiles[i].scan_held_min = held;
   g_s01_profiles[i].scan_flat_min = flat;
   g_s01_profiles[i].be_at_r = be;
   g_s01_profiles[i].comm_on = comm;
   g_s01_profiles[i].sessions = sessions;
   g_s01_profiles[i].hard_gate = hard_gate;
   g_s01_profiles[i].preferred = pref;
   g_s01_profiles[i].trail_n = 0;
   for(int k = 0; k < 4; k++)
     {
      g_s01_profiles[i].trail_at[k] = 0.0;
      g_s01_profiles[i].trail_dist[k] = 0.0;
     }
  }

//+------------------------------------------------------------------+
void S01Trail4(const int i,
               const double a0, const double d0,
               const double a1, const double d1,
               const double a2, const double d2,
               const double a3, const double d3)
  {
   g_s01_profiles[i].trail_n = 4;
   g_s01_profiles[i].trail_at[0] = a0;
   g_s01_profiles[i].trail_dist[0] = d0;
   g_s01_profiles[i].trail_at[1] = a1;
   g_s01_profiles[i].trail_dist[1] = d1;
   g_s01_profiles[i].trail_at[2] = a2;
   g_s01_profiles[i].trail_dist[2] = d2;
   g_s01_profiles[i].trail_at[3] = a3;
   g_s01_profiles[i].trail_dist[3] = d3;
  }

//+------------------------------------------------------------------+
void S01Trail3(const int i,
               const double a0, const double d0,
               const double a1, const double d1,
               const double a2, const double d2)
  {
   g_s01_profiles[i].trail_n = 3;
   g_s01_profiles[i].trail_at[0] = a0;
   g_s01_profiles[i].trail_dist[0] = d0;
   g_s01_profiles[i].trail_at[1] = a1;
   g_s01_profiles[i].trail_dist[1] = d1;
   g_s01_profiles[i].trail_at[2] = a2;
   g_s01_profiles[i].trail_dist[2] = d2;
   g_s01_profiles[i].trail_at[3] = 0.0;
   g_s01_profiles[i].trail_dist[3] = 0.0;
  }

//+------------------------------------------------------------------+
// Profiles copied from the Strategy-01 DEMO pack. USDCAD stays a
// trend-pullback entry; the mean-revert label is not a signal.
void S01ProfilesInit()
  {
   S01Fill(0, "USDJPY", "trend_pullback", 0.01, 12.0, 0.8, -0.054, 0.005, 45, 3, 5, 0.6, true, S01_ASIA | S01_LONDON, S01_HARD_NONE, S01_PREF_HKFX);
   S01Trail4(0, 0.5, 1.0, 1.0, 0.7, 2.0, 0.5, 3.0, 0.4);

   S01Fill(1, "EURUSD", "trend_pullback", 0.0001, 8.0, 0.8, 0.090, 0.006, 60, 3, 5, 0.6, true, S01_ASIA | S01_LONDON, S01_HARD_NONE, S01_PREF_HKFX);
   S01Trail4(1, 0.5, 0.9, 1.0, 0.7, 2.0, 0.5, 3.0, 0.35);

   S01Fill(2, "USDCAD", "mean_revert_fade", 0.0001, 10.0, 0.8, -0.595, 0.0025, 60, 3, 10, 0.4, true, S01_LONDON | S01_NY, S01_HARD_NONE, S01_PREF_HKFX);
   S01Trail3(2, 0.4, 0.5, 0.8, 0.35, 1.2, 0.25);

   S01Fill(3, "XAUUSD", "trend_pullback", 0.01, 300.0, 30.0, 0.039, 0.006, 45, 2, 5, 0.7, true, S01_ASIA | S01_LONDON, S01_HARD_NONE, S01_PREF_HKFX);
   S01Trail4(3, 0.5, 1.0, 1.0, 0.8, 2.0, 0.6, 3.0, 0.45);

   S01Fill(4, "NAS100", "breakout_momentum", 1.0, 40.0, 4.0, -0.025, 0.004, 30, 2, 5, 0.7, false, S01_NY, S01_HARD_US, S01_PREF_US);
   S01Trail3(4, 0.6, 1.0, 1.2, 0.7, 2.0, 0.5);

   S01Fill(5, "US500", "trend_pullback", 1.0, 8.0, 0.8, 0.036, 0.005, 30, 2, 5, 0.6, false, S01_NY, S01_HARD_US, S01_PREF_US);
   S01Trail3(5, 0.5, 0.9, 1.0, 0.7, 2.0, 0.5);

   S01Fill(6, "JPN225", "trend_pullback", 1.0, 120.0, 10.0, 0.123, 0.008, 30, 2, 5, 0.6, false, S01_ASIA, S01_HARD_TKY, S01_PREF_TKY);
   S01Trail4(6, 0.5, 1.0, 1.0, 0.8, 2.0, 0.6, 3.0, 0.45);

   S01Fill(7, "BTCUSD", "trend_pullback", 1.0, 200.0, 30.0, 0.069, 0.006, 60, 5, 15, 0.7, false, S01_ASIA | S01_LONDON | S01_NY, S01_HARD_BTC, S01_PREF_ANY);
   S01Trail4(7, 0.5, 1.0, 1.0, 0.8, 2.0, 0.6, 3.0, 0.5);
  }

//+------------------------------------------------------------------+
datetime S01NowHkt()
  {
   return(TimeGMT() + 8 * 3600);
  }

//+------------------------------------------------------------------+
datetime S01WeekStartHkt(const datetime hkt)
  {
   MqlDateTime dt;
   TimeToStruct(hkt, dt);
   int since_mon = (dt.day_of_week == 0) ? 6 : dt.day_of_week - 1;
   return(hkt - (datetime)since_mon * 86400 - (datetime)dt.hour * 3600
          - (datetime)dt.min * 60 - (datetime)dt.sec);
  }

//+------------------------------------------------------------------+
int S01SessionBucket(const int mins)
  {
   if(mins >= 7 * 60 && mins < 15 * 60)
      return(S01_ASIA);
   if(mins >= 15 * 60 && mins < 21 * 60)
      return(S01_LONDON);
   return(S01_NY);
  }

//+------------------------------------------------------------------+
bool S01InUsCash(const int mins)
  {
   return((mins >= 22 * 60 + 30) || (mins < 5 * 60));
  }

//+------------------------------------------------------------------+
bool S01InTokyo(const int mins)
  {
   return(mins >= 8 * 60 && mins < 14 * 60);
  }

//+------------------------------------------------------------------+
bool S01InHkFx(const int mins)
  {
   return(mins >= 15 * 60 && mins < 24 * 60);
  }

//+------------------------------------------------------------------+
string S01SessionReason(const S01Profile &p, const datetime hkt, bool &cautious)
  {
   cautious = false;
   MqlDateTime dt;
   TimeToStruct(hkt, dt);
   int mins = dt.hour * 60 + dt.min;

   if(p.hard_gate == S01_HARD_BTC)
     {
      if(dt.day_of_week != 0 && dt.day_of_week != 6)
         return("WEEKDAY_BTC_SKIP");
     }
   else if(p.hard_gate == S01_HARD_US)
     {
      if(!S01InUsCash(mins))
         return("OUTSIDE_US_CASH_SKIP");
     }
   else if(p.hard_gate == S01_HARD_TKY)
     {
      if(!S01InTokyo(mins))
         return("OUTSIDE_ASIA_TOKYO_SKIP");
     }

   int bucket = S01SessionBucket(mins);
   if((p.sessions & bucket) == 0)
      return("PROFILE_SESSION_SKIP");

   if(p.preferred == S01_PREF_HKFX && !S01InHkFx(mins))
      cautious = true;
   return("");
  }

//+------------------------------------------------------------------+
int S01RegimeDir(const double ema50, const double ema200, const double atr,
                 const double close, const double median_atr,
                 const double gap_mult, const double boom_mult)
  {
   if(atr <= 0.0 || ema50 <= 0.0 || ema200 <= 0.0 || close <= 0.0)
      return(0);
   if(MathAbs(ema50 - ema200) < gap_mult * atr)
      return(0);
   if(median_atr > 0.0 && boom_mult > 0.0 && atr > median_atr * boom_mult)
      return(0);
   if(ema50 > ema200 && close > ema50)
      return(1);
   if(ema50 < ema200 && close < ema50)
      return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
bool S01AtrStats(const double &series[], const int n, const double pct,
                 double &median, double &pct_value)
  {
   if(n < 5)
      return(false);
   double tmp[];
   ArrayResize(tmp, n);
   ArraySetAsSeries(tmp, false);
   for(int i = 0; i < n; i++)
     {
      if(series[i] <= 0.0 || series[i] == EMPTY_VALUE)
         return(false);
      tmp[i] = series[i];
     }
   ArraySort(tmp);
   if((n % 2) == 1)
      median = tmp[n / 2];
   else
      median = 0.5 * (tmp[n / 2 - 1] + tmp[n / 2]);

   double pos = pct * (double)(n - 1);
   if(pos < 0.0)
      pos = 0.0;
   if(pos > (double)(n - 1))
      pos = (double)(n - 1);
   int i0 = (int)MathFloor(pos);
   int i1 = (int)MathCeil(pos);
   if(i0 < 0)
      i0 = 0;
   if(i1 >= n)
      i1 = n - 1;
   if(i0 >= n)
      i0 = n - 1;
   if(i0 == i1)
      pct_value = tmp[i0];
   else
     {
      double w = pos - (double)i0;
      pct_value = tmp[i0] * (1.0 - w) + tmp[i1] * w;
     }
   return(true);
  }

//+------------------------------------------------------------------+
double S01StructureDist(const int dir, const double entry,
                        const double swing_low, const double swing_high,
                        const double atr, const double atr_mult,
                        const double swing_buffer)
  {
   if(entry <= 0.0 || atr <= 0.0 || atr_mult <= 0.0)
      return(0.0);
   if(dir > 0)
     {
      double sl_swing = swing_low - swing_buffer * atr;
      double sl_atr = entry - atr_mult * atr;
      double sl = MathMax(sl_swing, sl_atr);
      double dist = entry - sl;
      if(dist <= 0.0)
         dist = atr_mult * atr;
      return(dist);
     }
   if(dir < 0)
     {
      double sl_swing = swing_high + swing_buffer * atr;
      double sl_atr = entry + atr_mult * atr;
      double sl = MathMin(sl_swing, sl_atr);
      double dist = sl - entry;
      if(dist <= 0.0)
         dist = atr_mult * atr;
      return(dist);
     }
   return(0.0);
  }

//+------------------------------------------------------------------+
double S01ApplyFloors(const double structure_dist, const double min_sl_price,
                      const double atr_m30, const double atr_mult)
  {
   double dist = structure_dist;
   if(dist < 0.0)
      dist = 0.0;
   if(min_sl_price > dist)
      dist = min_sl_price;
   if(atr_m30 > 0.0 && atr_mult > 0.0)
     {
      double floor_dist = atr_mult * atr_m30;
      if(floor_dist > dist)
         dist = floor_dist;
     }
   return(dist);
  }

//+------------------------------------------------------------------+
double S01RiskFraction(const double profile_risk, const double kelly_sim,
                       const double f_star, const double global_cap,
                       const double input_frac)
  {
   double cap = 0.01;
   if(global_cap > 0.0 && global_cap < cap)
      cap = global_cap;
   double quarter_f = 0.25 * f_star;
   if(quarter_f > 0.0 && quarter_f < cap)
      cap = quarter_f;
   if(input_frac > 0.0 && input_frac < cap)
      cap = input_frac;
   double frac = profile_risk;
   if(frac > cap)
      frac = cap;
   if(frac < 0.0)
      frac = 0.0;
   if(kelly_sim > 0.0)
     {
      double qk = 0.25 * kelly_sim;
      if(qk < frac)
         frac = qk;
     }
   return(frac);
  }

//+------------------------------------------------------------------+
double S01FloorLots(const double risk_usd, const double per_lot,
                    const double step, const double min_lot, const double max_lot)
  {
   if(risk_usd <= 0.0 || per_lot <= 0.0 || step <= 0.0)
      return(0.0);
   double steps_d = risk_usd / per_lot / step;
   long steps = (long)MathFloor(steps_d + 1e-8);
   long cap = 0;
   if(max_lot > 0.0)
      cap = (long)MathFloor(max_lot / step + 1e-8);
   if(steps < 0)
      steps = 0;
   if(((double)steps + 1.0) * step * per_lot <= risk_usd + 1e-6)
     {
      if(cap <= 0 || steps + 1 <= cap)
         steps++;
     }
   while(steps > 0 && (double)steps * step * per_lot > risk_usd + 1e-6)
      steps--;
   if(cap > 0 && steps > cap)
      steps = cap;
   while(steps > 0 && (double)steps * step * per_lot > risk_usd + 1e-6)
      steps--;
   if(steps < 1)
      return(0.0);
   double lots = (double)steps * step;
   if(lots + 1e-10 < min_lot)
      return(0.0);
   return(lots);
  }

//+------------------------------------------------------------------+
// Rungs: first, first+step, first+2*step, ... Jump to the highest
// rung whose threshold is still <= peak. Default 50, 150, 250, ...
double S01HighestRung(const double peak, const double first, const double step)
  {
   if(first <= 0.0 || step <= 0.0)
      return(0.0);
   if(peak + 1e-9 < first)
      return(0.0);
   double k = MathFloor((peak - first) / step + 1e-12);
   if(k < 0.0)
      k = 0.0;
   return(first + k * step);
  }

//+------------------------------------------------------------------+
double S01UsdLockPrice(const int dir, const double entry, const double money_per_unit,
                       const double rung, const double lock_back, const double extra_cost)
  {
   if(dir == 0 || entry <= 0.0 || money_per_unit <= 0.0 || rung <= 0.0)
      return(0.0);
   double need = rung - lock_back + extra_cost;
   if(need < 0.0)
      need = 0.0;
   double sl = (dir > 0) ? entry + need / money_per_unit : entry - need / money_per_unit;
   if(sl <= 0.0)
      return(0.0);
   return(sl);
  }

//+------------------------------------------------------------------+
double S01RTrailPrice(const int dir, const double entry, const double r_dist,
                      const double peak_price, const double peak_net,
                      const bool enabled, const double min_peak_usd,
                      const S01Profile &p)
  {
   if(!enabled || r_dist <= 0.0 || entry <= 0.0 || peak_price <= 0.0)
      return(0.0);
   if(peak_net < min_peak_usd)
      return(0.0);
   double peak_r = 0.0;
   if(dir > 0)
      peak_r = (peak_price - entry) / r_dist;
   else if(dir < 0)
      peak_r = (entry - peak_price) / r_dist;
   else
      return(0.0);
   if(peak_r <= 0.0)
      return(0.0);

   bool any = false;
   double best = 0.0;
   if(p.be_at_r > 0.0 && peak_r + 1e-12 >= p.be_at_r)
     {
      best = entry;
      any = true;
     }
   int n = p.trail_n;
   if(n > 4)
      n = 4;
   for(int i = 0; i < n; i++)
     {
      if(peak_r + 1e-12 < p.trail_at[i])
         continue;
      double sl = (dir > 0) ? peak_price - p.trail_dist[i] * r_dist
                            : peak_price + p.trail_dist[i] * r_dist;
      if(sl <= 0.0)
         continue;
      if(!any)
        {
         best = sl;
         any = true;
        }
      else if(dir > 0)
         best = MathMax(best, sl);
      else
         best = MathMin(best, sl);
     }
   if(!any)
      return(0.0);
   return(best);
  }

//+------------------------------------------------------------------+
double S01TighterStop(const int dir, const double a, const double b)
  {
   bool ha = (a > 0.0);
   bool hb = (b > 0.0);
   if(!ha && !hb)
      return(0.0);
   if(ha && !hb)
      return(a);
   if(hb && !ha)
      return(b);
   if(dir > 0)
      return(MathMax(a, b));
   return(MathMin(a, b));
  }

//+------------------------------------------------------------------+
#endif
