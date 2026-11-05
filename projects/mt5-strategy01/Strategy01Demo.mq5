//+------------------------------------------------------------------+
//| Strategy01Demo.mq5                                               |
//| Strategy-01 DEMO Expert Advisor.                                 |
//| Refuses ACCOUNT_TRADE_MODE_REAL. Never point this at a live      |
//| account. No API tokens, passwords, or broker secrets.           |
//|                                                                  |
//| Rules follow the Strategy-01 DEMO pack: M30+M15 regime, M5       |
//| pullback, hard SL, Kelly-style size, USD rung lock.             |
//| Approximations vs the cTrader path are listed in README.md.     |
//+------------------------------------------------------------------+
#property copyright "Strategy-01 DEMO"
#property version   "1.00"
#property description "DEMO only. Refuses real accounts. M30+M15 regime, M5 pullback, hard SL, USD rung lock."

#include <Trade/Trade.mqh>

input group "帳戶（只限 DEMO）"
input long   InpDemoLogin          = 5360748;    // 預期 DEMO 帳戶（0＝只擋真實帳戶）
input long   InpBlockedLiveLogin   = 1401957;    // Live 黑名單（見到就停手）
input ulong  InpMagic              = 26010401;   // Magic（只管理這個編號）
input bool   InpChartOnly          = false;      // true＝只交易目前圖表
input string InpSuffix             = "";         // 品種後綴（例如 .a 或 m）
input bool   InpEnableEntries      = true;       // 允許新開倉（false 仍管理舊倉）

input group "品種（Pepperstone 風格，留空＝多品種模式停用）"
input string InpSymXau             = "XAUUSD";   // XAUUSD 名稱
input string InpSymBtc             = "BTCUSD";   // BTCUSD 名稱
input string InpSymEur             = "EURUSD";   // EURUSD 名稱
input string InpSymJpy             = "USDJPY";   // USDJPY 名稱
input string InpSymCad             = "USDCAD";   // USDCAD 名稱
input string InpSymNas             = "NAS100";   // NAS100 名稱
input string InpSymUs500           = "US500";    // US500 名稱
input string InpSymJpn             = "JPN225";   // JPN225 名稱

input group "風險與手數"
input double InpRiskFrac           = 0.01;       // risk_frac 上限（0＝不額外收緊）
input double InpFStar              = 0.126;      // Kelly f*（0＝不用 1/4 f*）
input double InpGlobalRiskCap      = 0.01;       // 全局硬頂（大於 1% 也會夾到 1%）
input double InpAtrFloorE          = 1.5;        // E：止損地板 × M30 ATR14（非 EURUSD）
input double InpAtrFloorF          = 2.0;        // F：止損地板 × M30 ATR14（只 EURUSD）
input double InpLotStep            = 0.01;       // 手數步長
input double InpMinLot             = 0.01;       // 最小手數
input double InpCommissionBufferUsd = 7.0;       // 來回佣金緩衝（USD／手）
input double InpWeeklyKillPct      = -5.0;       // 週熔斷（-5＝跌 5% 停新開）
input double InpWeekRefEquity      = 0.0;        // 週參考權益（0＝本週首次自動記淨值）
input bool   InpUseBalance         = false;      // true＝用餘額計風險，false＝用淨值

input group "進場（DEMO_RELAXED 預設）"
input int    InpPullbackBars       = 24;         // M5 回撤回看根數
input double InpNearZoneAtr        = 0.5;        // 近區（× M5 ATR）
input double InpChaseHardAtr       = 2.0;        // 追價硬擋（× M5 ATR）
input double InpChaseSoftAtr       = 1.2;        // 追價軟標（× M5 ATR）
input double InpStructureAtrMult   = 1.5;        // 結構止損（× M5 ATR）
input double InpSwingBufferAtr     = 0.1;        // 擺動緩衝（× M5 ATR）
input double InpSlAbandonAtr       = 0.4;        // 止損窄過這個倍數就放棄
input double InpDriftVsSl          = 0.5;        // 現價偏離超過幾倍止損就放棄
input double InpSlKeepFrac         = 0.80;       // 實際止損至少保留訊號距離的比例

input group "Muse 閘"
input double InpSqueezePct         = 0.20;       // Squeeze 分位（0.20 或 20）
input int    InpAtrStatsBars       = 60;         // ATR 樣本根數
input int    InpExpandBars         = 10;         // 擴張突破根數 N
input double InpChopRatio          = 0.5;        // Chop：|EMA50-EMA200|/ATR 小於此值
input double InpRegimeGapAtr       = 0.15;       // 制度最小 EMA 差距（× ATR）
input double InpRegimeBoom         = 2.2;        // ATR 大於中位數的這個倍數則制度關閉

input group "出場鎖利"
input double InpRungFirstUsd       = 50.0;       // 第一檔（帳戶貨幣）
input double InpRungStepUsd        = 100.0;      // 其後每檔步長
input double InpRungLockBackUsd    = 30.0;       // 鎖定目標＝檔位減這個數
input bool   InpUseRTrail          = true;       // 啟用 R 移動止損（與檔位取較緊）
input double InpRTrailMinPeakUsd   = 100.0;      // R 軌啟用所需峰值淨浮盈
input double InpHotFloatUsd        = 50.0;       // 達到後鎖利改單最多等 2 秒
input bool   InpUseFarTp           = false;      // 啟用遠端止盈（非主出場）
input double InpFarTpR             = 3.0;        // 遠端止盈 R 倍數

input group "執行"
input int    InpDeviationPoints    = 30;         // 最大滑點（點）

#include "Include/S01Engine.mqh"

CTrade   g_trade;
S01Sym   g_syms[S01_COUNT];
int      g_count = 0;
bool     g_halt = false;
bool     g_hard_halt = false;
string   g_halt_why = "";
bool     g_seen_ready = false;
bool     g_week_kill = false;
double   g_week_dd = 0.0;
double   g_week_ref = 0.0;
datetime g_week_start = 0;
bool     g_currency_warned = false;

double   g_pend_r[S01_COUNT];
datetime g_pend_until[S01_COUNT];

ulong    g_seen[64];
int      g_seen_n = 0;

string   g_once[128];
int      g_once_n = 0;

ulong    g_mod_ticket[16];
datetime g_mod_time[16];
datetime g_mod_fail[16];

//+------------------------------------------------------------------+
string S01ValidateInputs()
  {
   if(InpMagic == 0)
      return("magic");
   if(InpLotStep <= 0.0 || InpMinLot <= 0.0)
      return("lots");
   if(InpRungFirstUsd <= 0.0 || InpRungStepUsd <= 0.0)
      return("rung");
   if(InpRungLockBackUsd < 0.0 || InpRungLockBackUsd >= InpRungFirstUsd)
      return("lock back must be smaller than the first rung");
   if(InpWeeklyKillPct >= 0.0)
      return("weekly kill must be negative");
   if(InpPullbackBars < 5 || InpPullbackBars > 200)
      return("pullback bars");
   if(InpExpandBars < 2 || InpExpandBars > 50)
      return("expand bars");
   if(InpAtrStatsBars < 20 || InpAtrStatsBars > 300)
      return("atr stats");
   if(InpChaseHardAtr > 0.0 && InpChaseSoftAtr > InpChaseHardAtr)
      return("chase soft is above chase hard");
   if(InpAtrFloorE < 0.0 || InpAtrFloorF < 0.0)
      return("atr floor");
   if(InpCommissionBufferUsd < 0.0)
      return("commission");
   if(InpFStar < 0.0 || InpRiskFrac < 0.0 || InpGlobalRiskCap < 0.0)
      return("risk");
   if(InpSlKeepFrac < 0.0 || InpSlKeepFrac > 100.0)
      return("sl keep fraction");
   if(InpDriftVsSl < 0.0 || InpNearZoneAtr < 0.0)
      return("drift");
   if(InpHotFloatUsd < 0.0 || InpDeviationPoints < 0)
      return("execution");
   if(InpFarTpR < 0.0 || InpWeekRefEquity < 0.0)
      return("tp or week ref");
   if(InpStructureAtrMult < 0.0 || InpSwingBufferAtr < 0.0 || InpSlAbandonAtr < 0.0)
      return("structure");
   if(InpRegimeGapAtr < 0.0 || InpRegimeBoom < 0.0 || InpChopRatio < 0.0)
      return("regime");
   return("");
  }

//+------------------------------------------------------------------+
string S01InputName(const string key)
  {
   if(key == "XAUUSD")
      return(InpSymXau);
   if(key == "BTCUSD")
      return(InpSymBtc);
   if(key == "EURUSD")
      return(InpSymEur);
   if(key == "USDJPY")
      return(InpSymJpy);
   if(key == "USDCAD")
      return(InpSymCad);
   if(key == "NAS100")
      return(InpSymNas);
   if(key == "US500")
      return(InpSymUs500);
   if(key == "JPN225")
      return(InpSymJpn);
   return("");
  }

//+------------------------------------------------------------------+
int S01FillAliases(const string key, string &out[])
  {
   ArrayResize(out, 4);
   int n = 0;
   if(key == "XAUUSD")
      out[n++] = "GOLD";
   else if(key == "BTCUSD")
      out[n++] = "BTCUSDT";
   else if(key == "NAS100")
     {
      out[n++] = "US100";
      out[n++] = "USTEC";
     }
   else if(key == "US500")
     {
      out[n++] = "SPX500";
      out[n++] = "SP500";
     }
   else if(key == "JPN225")
      out[n++] = "JP225";
   return(n);
  }

//+------------------------------------------------------------------+
bool S01AccountOk(string &why)
  {
   why = "";
   bool tester = (MQLInfoInteger(MQL_TESTER) != 0);
   long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   if(mode == ACCOUNT_TRADE_MODE_REAL)
     {
      why = "REAL";
      g_hard_halt = true;
      return(false);
     }
   if(InpBlockedLiveLogin != 0 && login == InpBlockedLiveLogin)
     {
      why = "LIVE_LOGIN";
      g_hard_halt = true;
      return(false);
     }
   if(!tester && InpDemoLogin != 0 && login != InpDemoLogin)
     {
      why = "WRONG_LOGIN";
      g_hard_halt = true;
      return(false);
     }
   if(!tester && !TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      why = "LOGOUT";
      return(false);
     }
   if(!tester && login == 0)
     {
      why = "NO_LOGIN";
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
void S01AlertHalt(const string why)
  {
   string msg = "錯戶／Live 停手";
   if(why == "LOGOUT" || why == "NO_LOGIN")
      msg = "登出停手";
   Alert(msg);
   Print("Strategy-01 ", msg, " (", why, ")");
  }

//+------------------------------------------------------------------+
void S01RefreshHalt()
  {
   string why;
   bool ok = S01AccountOk(why);
   if(!ok && !g_halt)
     {
      g_halt = true;
      g_halt_why = why;
      S01AlertHalt(why);
     }
   else if(ok && g_halt && !g_hard_halt)
     {
      g_halt = false;
      g_halt_why = "";
      Print("Strategy-01 resumed on DEMO login ", AccountInfoInteger(ACCOUNT_LOGIN));
     }
  }

//+------------------------------------------------------------------+
string S01Gv(const string tag, const ulong id)
  {
   return(StringFormat("S01%s_%I64u_%I64u", tag, InpMagic, id));
  }

//+------------------------------------------------------------------+
string S01WeekGv(const datetime week_start)
  {
   return(StringFormat("S01W_%I64u_%I64d", InpMagic, (long)week_start));
  }

//+------------------------------------------------------------------+
string S01KillGv(const datetime week_start)
  {
   return(StringFormat("S01K_%I64u_%I64d", InpMagic, (long)week_start));
  }

//+------------------------------------------------------------------+
void S01GvSet(const string key, const double value)
  {
   if(GlobalVariableSet(key, value))
      return;
   static bool told = false;
   if(!told)
     {
      Print("Strategy-01 GlobalVariableSet failed. Peak memory may reset. err=", GetLastError());
      told = true;
     }
  }

//+------------------------------------------------------------------+
void S01UpdateWeek()
  {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   datetime hkt = S01NowHkt();
   g_week_start = S01WeekStartHkt(hkt);
   if(InpWeekRefEquity > 0.0)
      g_week_ref = InpWeekRefEquity;
   else
     {
      string key = S01WeekGv(g_week_start);
      if(GlobalVariableCheck(key))
         g_week_ref = GlobalVariableGet(key);
      else
        {
         g_week_ref = equity;
         S01GvSet(key, g_week_ref);
         Print("Strategy-01 week reference equity ", DoubleToString(g_week_ref, 2));
        }
     }
   g_week_dd = 0.0;
   if(g_week_ref > 0.0)
      g_week_dd = (equity - g_week_ref) / g_week_ref * 100.0;

   string kill_key = S01KillGv(g_week_start);
   if(GlobalVariableCheck(kill_key))
     {
      g_week_kill = true;
      return;
     }
   if(g_week_ref > 0.0 && g_week_dd <= InpWeeklyKillPct)
     {
      g_week_kill = true;
      S01GvSet(kill_key, g_week_dd);
      string msg = StringFormat("週熔斷 %+.1f%% 停新開", g_week_dd);
      Alert(msg);
      Print("Strategy-01 ", msg);
      return;
     }
   g_week_kill = false;
  }

//+------------------------------------------------------------------+
void S01ClearSym(S01Sym &sx)
  {
   sx.profile = -1;
   sx.symbol = "";
   sx.active = false;
   sx.h_m30_ema20 = INVALID_HANDLE;
   sx.h_m30_ema50 = INVALID_HANDLE;
   sx.h_m30_ema200 = INVALID_HANDLE;
   sx.h_m30_atr = INVALID_HANDLE;
   sx.h_m15_ema50 = INVALID_HANDLE;
   sx.h_m15_ema200 = INVALID_HANDLE;
   sx.h_m15_atr = INVALID_HANDLE;
   sx.h_m5_ema20 = INVALID_HANDLE;
   sx.h_m5_atr = INVALID_HANDLE;
   sx.last_m5 = 0;
   sx.last_eval = 0;
   sx.sent_bar = 0;
   sx.attempt_bar = 0;
   sx.data_retry = 0;
   sx.last_reason = "";
  }

//+------------------------------------------------------------------+
void S01Rel(int &handle)
  {
   if(handle != INVALID_HANDLE)
     {
      IndicatorRelease(handle);
      handle = INVALID_HANDLE;
     }
  }

//+------------------------------------------------------------------+
void S01ReleaseSym(S01Sym &sx)
  {
   S01Rel(sx.h_m30_ema20);
   S01Rel(sx.h_m30_ema50);
   S01Rel(sx.h_m30_ema200);
   S01Rel(sx.h_m30_atr);
   S01Rel(sx.h_m15_ema50);
   S01Rel(sx.h_m15_ema200);
   S01Rel(sx.h_m15_atr);
   S01Rel(sx.h_m5_ema20);
   S01Rel(sx.h_m5_atr);
  }

//+------------------------------------------------------------------+
bool S01CreateIndicators(S01Sym &sx)
  {
   string s = sx.symbol;
   sx.h_m30_ema20 = iMA(s, PERIOD_M30, 20, 0, MODE_EMA, PRICE_CLOSE);
   sx.h_m30_ema50 = iMA(s, PERIOD_M30, 50, 0, MODE_EMA, PRICE_CLOSE);
   sx.h_m30_ema200 = iMA(s, PERIOD_M30, 200, 0, MODE_EMA, PRICE_CLOSE);
   sx.h_m30_atr = iATR(s, PERIOD_M30, 14);
   sx.h_m15_ema50 = iMA(s, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   sx.h_m15_ema200 = iMA(s, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   sx.h_m15_atr = iATR(s, PERIOD_M15, 14);
   sx.h_m5_ema20 = iMA(s, PERIOD_M5, 20, 0, MODE_EMA, PRICE_CLOSE);
   sx.h_m5_atr = iATR(s, PERIOD_M5, 14);
   int hs[9];
   hs[0] = sx.h_m30_ema20;
   hs[1] = sx.h_m30_ema50;
   hs[2] = sx.h_m30_ema200;
   hs[3] = sx.h_m30_atr;
   hs[4] = sx.h_m15_ema50;
   hs[5] = sx.h_m15_ema200;
   hs[6] = sx.h_m15_atr;
   hs[7] = sx.h_m5_ema20;
   hs[8] = sx.h_m5_atr;
   for(int i = 0; i < 9; i++)
     {
      if(hs[i] == INVALID_HANDLE)
         return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
bool S01TrySelect(const string name)
  {
   if(StringLen(name) == 0)
      return(false);
   ResetLastError();
   if(!SymbolInfoInteger(name, SYMBOL_EXIST))
      return(false);
   return(SymbolSelect(name, true));
  }

//+------------------------------------------------------------------+
string S01WithSuffix(const string base)
  {
   if(StringLen(base) == 0)
      return("");
   if(StringLen(InpSuffix) == 0)
      return(base);
   int n = StringLen(InpSuffix);
   if(StringLen(base) >= n && StringSubstr(base, StringLen(base) - n) == InpSuffix)
      return(base);
   return(base + InpSuffix);
  }

//+------------------------------------------------------------------+
void S01Push(string &arr[], int &n, const int cap, const string value)
  {
   if(n >= cap || StringLen(value) == 0)
      return;
   for(int i = 0; i < n; i++)
     {
      if(arr[i] == value)
         return;
     }
   arr[n] = value;
   n++;
  }

//+------------------------------------------------------------------+
string S01Resolve(const int pi)
  {
   string input = S01InputName(g_s01_profiles[pi].key);
   if(StringLen(input) == 0)
      return("");
   string alias[];
   int na = S01FillAliases(g_s01_profiles[pi].key, alias);
   string cands[];
   ArrayResize(cands, 16);
   int n = 0;
   S01Push(cands, n, 16, S01WithSuffix(input));
   S01Push(cands, n, 16, input);
   S01Push(cands, n, 16, S01WithSuffix(g_s01_profiles[pi].key));
   S01Push(cands, n, 16, g_s01_profiles[pi].key);
   for(int a = 0; a < na; a++)
     {
      S01Push(cands, n, 16, S01WithSuffix(alias[a]));
      S01Push(cands, n, 16, alias[a]);
     }
   for(int i = 0; i < n; i++)
     {
      if(S01TrySelect(cands[i]))
         return(cands[i]);
     }
   return("");
  }

//+------------------------------------------------------------------+
bool S01NameMatch(const string chart, const string base)
  {
   if(StringLen(base) == 0 || StringLen(chart) == 0)
      return(false);
   string c = chart;
   string b = base;
   StringToUpper(c);
   StringToUpper(b);
   if(c == b)
      return(true);
   string core = c;
   int dot = StringFind(core, ".");
   if(dot > 0)
      core = StringSubstr(core, 0, dot);
   int dash = StringFind(core, "-");
   if(dash > 0)
      core = StringSubstr(core, 0, dash);
   if(core == b)
      return(true);
   if(StringLen(InpSuffix) > 0)
     {
      string suf = InpSuffix;
      StringToUpper(suf);
      if(StringLen(c) > StringLen(suf) && StringSubstr(c, StringLen(c) - StringLen(suf)) == suf)
        {
         if(StringSubstr(c, 0, StringLen(c) - StringLen(suf)) == b)
            return(true);
        }
     }
   if(StringLen(core) == StringLen(b) + 1 && StringFind(core, b) == 0)
     {
      if(StringGetCharacter(core, StringLen(b)) == 'M')
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
int S01MatchProfile(const string chart)
  {
   for(int i = 0; i < S01_COUNT; i++)
     {
      if(S01NameMatch(chart, g_s01_profiles[i].key))
         return(i);
      if(S01NameMatch(chart, S01InputName(g_s01_profiles[i].key)))
         return(i);
      string alias[];
      int na = S01FillAliases(g_s01_profiles[i].key, alias);
      for(int a = 0; a < na; a++)
        {
         if(S01NameMatch(chart, alias[a]))
            return(i);
        }
     }
   return(-1);
  }

//+------------------------------------------------------------------+
bool S01BuildSymbols()
  {
   g_count = 0;
   for(int i = 0; i < S01_COUNT; i++)
      S01ClearSym(g_syms[i]);

   if(InpChartOnly)
     {
      int pi = S01MatchProfile(_Symbol);
      if(pi < 0)
        {
         Print("Strategy-01 chart symbol ", _Symbol, " matches no profile. Expected XAUUSD BTCUSD EURUSD USDJPY USDCAD NAS100 US500 JPN225.");
         return(false);
        }
      if(!S01TrySelect(_Symbol))
        {
         Print("Strategy-01 cannot select ", _Symbol);
         return(false);
        }
      g_syms[0].symbol = _Symbol;
      g_syms[0].profile = pi;
      g_syms[0].active = true;
      g_count = 1;
      return(true);
     }

   for(int pi = 0; pi < S01_COUNT; pi++)
     {
      string typed = S01InputName(g_s01_profiles[pi].key);
      string name = S01Resolve(pi);
      if(StringLen(name) == 0)
        {
         if(StringLen(typed) > 0)
            Print("Strategy-01 symbol not found: ", g_s01_profiles[pi].key, " / ", typed);
         continue;
        }
      bool dup = false;
      for(int j = 0; j < g_count; j++)
        {
         if(g_syms[j].symbol == name)
            dup = true;
        }
      if(dup)
         continue;
      g_syms[g_count].symbol = name;
      g_syms[g_count].profile = pi;
      g_syms[g_count].active = true;
      g_count++;
     }
   if(g_count == 0)
     {
      Print("Strategy-01 resolved no symbols. Check Market Watch names and the suffix input.");
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
void S01ConfigureFilling(const string symbol)
  {
   long flags = SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   if((flags & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((flags & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      g_trade.SetTypeFilling(ORDER_FILLING_RETURN);
  }

//+------------------------------------------------------------------+
string S01IdKey(const string prefix, const ulong id)
  {
   return(prefix + IntegerToString((long)id));
  }

//+------------------------------------------------------------------+
bool S01Once(const string key)
  {
   for(int i = 0; i < g_once_n; i++)
     {
      if(g_once[i] == key)
         return(false);
     }
   if(g_once_n >= 128)
     {
      for(int i = 0; i < 127; i++)
         g_once[i] = g_once[i + 1];
      g_once_n = 127;
     }
   g_once[g_once_n] = key;
   g_once_n++;
   return(true);
  }

//+------------------------------------------------------------------+
void S01ForgetPosition(const ulong id)
  {
   GlobalVariableDel(S01Gv("R", id));
   GlobalVariableDel(S01Gv("P", id));
   GlobalVariableDel(S01Gv("X", id));
   GlobalVariableDel(S01Gv("G", id));
  }

//+------------------------------------------------------------------+
void S01AlertOpen(const string sym, const long deal_type)
  {
   string side = (deal_type == DEAL_TYPE_SELL) ? "空" : "好";
   string msg = sym + " " + side + "：開倉";
   Alert(msg);
   Print("Strategy-01 ", msg);
  }

//+------------------------------------------------------------------+
void S01AlertClose(const string sym, const double pnl)
  {
   string msg = StringFormat("%s 平倉：%+.2f", sym, pnl);
   Alert(msg);
   Print("Strategy-01 ", msg);
  }

//+------------------------------------------------------------------+
void S01AlertLock(const string sym, const double rung)
  {
   string msg = StringFormat("%s 鎖利 +%.0f", sym, rung);
   Alert(msg);
   Print("Strategy-01 ", msg);
  }

//+------------------------------------------------------------------+
double S01ClosedNet(const ulong position_id)
  {
   if(!HistorySelectByPosition(position_id))
      return(0.0);
   double pnl = 0.0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         continue;
      pnl += HistoryDealGetDouble(deal, DEAL_PROFIT);
      pnl += HistoryDealGetDouble(deal, DEAL_SWAP);
      pnl += HistoryDealGetDouble(deal, DEAL_COMMISSION);
     }
   return(pnl);
  }

//+------------------------------------------------------------------+
void S01NotePendingR(const int idx, const string symbol, const ulong position_id)
  {
   if(idx < 0 || idx >= S01_COUNT)
      return;
   if(g_pend_r[idx] <= 0.0 || TimeCurrent() > g_pend_until[idx])
      return;
   if(g_syms[idx].symbol != symbol && symbol != "")
      return;
   if(position_id == 0)
      return;
   S01GvSet(S01Gv("R", position_id), g_pend_r[idx]);
   g_pend_r[idx] = 0.0;
   g_pend_until[idx] = 0;
  }

//+------------------------------------------------------------------+
void S01OnDeal(const ulong deal)
  {
   if(deal == 0 || !HistoryDealSelect(deal))
      return;
   if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic)
      return;
   string sym = HistoryDealGetString(deal, DEAL_SYMBOL);
   long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
   ulong pid = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   if(entry == DEAL_ENTRY_IN)
     {
      for(int i = 0; i < g_count; i++)
        {
         if(g_syms[i].symbol == sym)
            S01NotePendingR(i, sym, pid);
        }
      long dtype = HistoryDealGetInteger(deal, DEAL_TYPE);
      if(S01Once(S01IdKey("O", pid)))
         S01AlertOpen(sym, dtype);
     }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY || entry == DEAL_ENTRY_INOUT)
     {
      if(PositionSelectByTicket(pid))
         return;
      if(S01Once(S01IdKey("C", pid)))
        {
         S01AlertClose(sym, S01ClosedNet(pid));
         S01ForgetPosition(pid);
        }
     }
  }

//+------------------------------------------------------------------+
int S01SeenSlot(const ulong ticket)
  {
   for(int i = 0; i < g_seen_n; i++)
     {
      if(g_seen[i] == ticket)
         return(i);
     }
   return(-1);
  }

//+------------------------------------------------------------------+
void S01SyncSeen()
  {
   ulong now_t[];
   ArrayResize(now_t, 64);
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if(n < 64)
        {
         now_t[n] = ticket;
         n++;
        }
     }
   if(!g_seen_ready)
     {
      g_seen_n = 0;
      for(int i = 0; i < n && i < 64; i++)
        {
         g_seen[g_seen_n] = now_t[i];
         g_seen_n++;
        }
      g_seen_ready = true;
      return;
     }
   for(int i = 0; i < n; i++)
     {
      if(S01SeenSlot(now_t[i]) >= 0)
         continue;
      if(!PositionSelectByTicket(now_t[i]))
         continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      long ptype = PositionGetInteger(POSITION_TYPE);
      long dtype = (ptype == POSITION_TYPE_SELL) ? DEAL_TYPE_SELL : DEAL_TYPE_BUY;
      if(S01Once(S01IdKey("O", now_t[i])))
         S01AlertOpen(sym, dtype);
     }
   for(int i = 0; i < g_seen_n; i++)
     {
      bool still = false;
      for(int j = 0; j < n; j++)
        {
         if(now_t[j] == g_seen[i])
            still = true;
        }
      if(still)
         continue;
      if(S01Once(S01IdKey("C", g_seen[i])))
        {
         string sym = "";
         if(HistorySelectByPosition(g_seen[i]))
           {
            int deals = HistoryDealsTotal();
            if(deals > 0)
              {
               ulong deal = HistoryDealGetTicket(deals - 1);
               sym = HistoryDealGetString(deal, DEAL_SYMBOL);
              }
           }
         S01AlertClose(sym, S01ClosedNet(g_seen[i]));
         S01ForgetPosition(g_seen[i]);
        }
     }
   g_seen_n = 0;
   for(int i = 0; i < n && i < 64; i++)
     {
      g_seen[g_seen_n] = now_t[i];
      g_seen_n++;
     }
  }

//+------------------------------------------------------------------+
bool S01SymbolHasPosition(const string symbol)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == symbol)
         return(true);
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) == symbol)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
bool S01InCooldown(const string symbol, const int minutes)
  {
   if(minutes <= 0)
      return(false);
   datetime now = TimeCurrent();
   datetime from = now - (datetime)minutes * 60;
   if(!HistorySelect(from, now))
      return(false);
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         continue;
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != symbol)
         continue;
      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic)
         continue;
      long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
         continue;
      long reason = HistoryDealGetInteger(deal, DEAL_REASON);
      if(reason != DEAL_REASON_SL && reason != DEAL_REASON_SO)
         continue;
      datetime when = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      return((now - when) < (datetime)minutes * 60);
     }
   return(false);
  }

//+------------------------------------------------------------------+
double S01PositionNet(const ulong ticket, const int profile_index)
  {
   double vol = PositionGetDouble(POSITION_VOLUME);
   double profit = PositionGetDouble(POSITION_PROFIT);
   double swap = PositionGetDouble(POSITION_SWAP);
   double comm = 0.0;
   if(profile_index >= 0 && profile_index < S01_COUNT && g_s01_profiles[profile_index].comm_on)
      comm = InpCommissionBufferUsd * vol;
   return(profit + swap - comm);
  }

//+------------------------------------------------------------------+
int S01ProfileOfSymbol(const string symbol)
  {
   for(int i = 0; i < g_count; i++)
     {
      if(g_syms[i].symbol == symbol)
         return(g_syms[i].profile);
     }
   return(S01MatchProfile(symbol));
  }

//+------------------------------------------------------------------+
int S01ModSlot(const ulong ticket, const bool create)
  {
   int free_slot = -1;
   for(int i = 0; i < 16; i++)
     {
      if(g_mod_ticket[i] == ticket)
         return(i);
      if(g_mod_ticket[i] == 0 && free_slot < 0)
         free_slot = i;
     }
   if(!create)
      return(-1);
   if(free_slot < 0)
      free_slot = 0;
   g_mod_ticket[free_slot] = ticket;
   g_mod_time[free_slot] = 0;
   g_mod_fail[free_slot] = 0;
   return(free_slot);
  }

//+------------------------------------------------------------------+
bool S01ModThrottled(const ulong ticket, const int wait_sec)
  {
   datetime now = TimeCurrent();
   int slot = S01ModSlot(ticket, false);
   if(slot >= 0 && g_mod_fail[slot] > 0 && (now - g_mod_fail[slot]) < 10)
      return(true);
   if(wait_sec <= 0 || slot < 0)
      return(false);
   if((now - g_mod_time[slot]) < wait_sec)
      return(true);
   return(false);
  }

//+------------------------------------------------------------------+
void S01ModStamp(const ulong ticket, const bool failed)
  {
   int slot = S01ModSlot(ticket, true);
   if(slot < 0)
      return;
   datetime now = TimeCurrent();
   if(failed)
      g_mod_fail[slot] = now;
   else
     {
      g_mod_time[slot] = now;
      g_mod_fail[slot] = 0;
     }
  }

//+------------------------------------------------------------------+
double S01ClampStop(const string symbol, const int dir, const double entry,
                    const double current_sl, const double proposed)
  {
   if(proposed <= 0.0)
      return(0.0);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int stops = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   int freeze = (int)SymbolInfoInteger(symbol, SYMBOL_FREEZE_LEVEL);
   int guard = stops;
   if(freeze > guard)
      guard = freeze;
   double min_dist = ((double)guard + 1.0) * point;
   if(min_dist < point)
      min_dist = point;
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double next = proposed;
   if(dir > 0)
     {
      double limit = bid - min_dist;
      if(next > limit)
        {
         if(current_sl > 0.0 && limit <= current_sl)
            return(0.0);
         if(proposed > entry && limit < entry)
            return(0.0);
         next = limit;
        }
      next = S01AlignStop(dir, symbol, next);
      if(next > limit)
         next = S01AlignWider(dir, symbol, limit);
      if(next > limit || next <= 0.0)
         return(0.0);
      if(current_sl > 0.0 && next <= current_sl + point * 0.5)
         return(0.0);
     }
   else
     {
      double limit = ask + min_dist;
      if(next < limit)
        {
         if(current_sl > 0.0 && limit >= current_sl)
            return(0.0);
         if(proposed < entry && limit > entry)
            return(0.0);
         next = limit;
        }
      next = S01AlignStop(dir, symbol, next);
      if(next < limit)
         next = S01AlignWider(dir, symbol, limit);
      if(next < limit || next <= 0.0)
         return(0.0);
      if(current_sl > 0.0 && next >= current_sl - point * 0.5)
         return(0.0);
     }
   if(next <= 0.0)
      return(0.0);
   return(next);
  }

//+------------------------------------------------------------------+
void S01CloseTicket(const ulong ticket, const string why)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   string sym = PositionGetString(POSITION_SYMBOL);
   S01ConfigureFilling(sym);
   Print("Strategy-01 close ", sym, " ", why);
   if(!g_trade.PositionClose(ticket))
      Print("Strategy-01 close failed ", g_trade.ResultRetcode(), " ", g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
void S01ManageOne(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
      return;
   string symbol = PositionGetString(POSITION_SYMBOL);
   long ptype = PositionGetInteger(POSITION_TYPE);
   int dir = 0;
   if(ptype == POSITION_TYPE_BUY)
      dir = 1;
   else if(ptype == POSITION_TYPE_SELL)
      dir = -1;
   else
      return;

   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double cur_sl = PositionGetDouble(POSITION_SL);
   double cur_tp = PositionGetDouble(POSITION_TP);
   double volume = PositionGetDouble(POSITION_VOLUME);
   int pi = S01ProfileOfSymbol(symbol);
   double net = S01PositionNet(ticket, pi);

   string peak_key = S01Gv("P", ticket);
   double peak_net = net;
   if(GlobalVariableCheck(peak_key))
      peak_net = MathMax(GlobalVariableGet(peak_key), net);
   S01GvSet(peak_key, peak_net);

   string rkey = S01Gv("R", ticket);
   if(cur_sl <= 0.0)
     {
      double recovered = 0.0;
      if(GlobalVariableCheck(rkey))
         recovered = GlobalVariableGet(rkey);
      if(recovered <= 0.0)
        {
         S01CloseTicket(ticket, "naked position has no hard SL");
         return;
        }
      double init_sl = (dir > 0) ? entry - recovered : entry + recovered;
      init_sl = S01AlignWider(dir, symbol, init_sl);
      init_sl = S01ClampStop(symbol, dir, entry, 0.0, init_sl);
      if(init_sl <= 0.0)
        {
         S01CloseTicket(ticket, "cannot restore hard SL");
         return;
        }
      S01ConfigureFilling(symbol);
      if(!g_trade.PositionModify(ticket, init_sl, cur_tp))
         S01CloseTicket(ticket, "SL restore rejected");
      return;
     }

   if(!GlobalVariableCheck(rkey))
     {
      bool loss_side = (dir > 0 && cur_sl < entry) || (dir < 0 && cur_sl > entry);
      if(loss_side)
         S01GvSet(rkey, MathAbs(entry - cur_sl));
     }

   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double px = (dir > 0) ? bid : ask;
   datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
   datetime m1 = iTime(symbol, PERIOD_M1, 0);
   if(m1 > 0 && m1 >= opened)
     {
      if(dir > 0)
        {
         double hi = iHigh(symbol, PERIOD_M1, 0);
         if(hi > 0.0)
            px = MathMax(px, hi);
        }
      else
        {
         double lo = iLow(symbol, PERIOD_M1, 0);
         if(lo > 0.0)
            px = MathMin(px, lo);
        }
     }
   string px_key = S01Gv("X", ticket);
   double peak_px = px;
   if(GlobalVariableCheck(px_key))
     {
      double stored_px = GlobalVariableGet(px_key);
      if(dir > 0)
         peak_px = MathMax(stored_px, px);
      else
         peak_px = MathMin(stored_px, px);
     }
   S01GvSet(px_key, peak_px);

   double rung = S01HighestRung(peak_net, InpRungFirstUsd, InpRungStepUsd);
   string rung_key = S01Gv("G", ticket);
   double rung_done = 0.0;
   if(GlobalVariableCheck(rung_key))
      rung_done = GlobalVariableGet(rung_key);

   double comm = 0.0;
   if(pi >= 0 && g_s01_profiles[pi].comm_on)
      comm = InpCommissionBufferUsd * volume;
   double mpu = S01MoneyPerUnit(symbol, dir, volume, entry);
   double usd_sl = S01UsdLockPrice(dir, entry, mpu, rung, InpRungLockBackUsd, comm);

   double r_dist = 0.0;
   if(GlobalVariableCheck(rkey))
      r_dist = GlobalVariableGet(rkey);
   double r_sl = 0.0;
   if(pi >= 0 && r_dist > 0.0)
      r_sl = S01RTrailPrice(dir, entry, r_dist, peak_px, peak_net,
                            InpUseRTrail, InpRTrailMinPeakUsd, g_s01_profiles[pi]);

   double want = S01TighterStop(dir, usd_sl, r_sl);
   if(want <= 0.0)
      return;
   want = S01ClampStop(symbol, dir, entry, cur_sl, want);
   if(want <= 0.0)
      return;

   int wait_sec = 15;
   if(peak_net >= InpHotFloatUsd)
      wait_sec = 2;
   if(rung > rung_done + 0.1)
      wait_sec = 0;
   if(S01ModThrottled(ticket, wait_sec))
      return;

   S01ConfigureFilling(symbol);
   if(!g_trade.PositionModify(ticket, want, cur_tp))
     {
      S01ModStamp(ticket, true);
      Print("Strategy-01 SL modify failed ", symbol, " ", g_trade.ResultRetcode(),
            " ", g_trade.ResultRetcodeDescription());
      return;
     }
   S01ModStamp(ticket, false);
   if(rung > rung_done + 0.1)
     {
      S01GvSet(rung_key, rung);
      S01AlertLock(symbol, rung);
     }
  }

//+------------------------------------------------------------------+
void S01ManagePositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      S01ManageOne(ticket);
     }
  }

//+------------------------------------------------------------------+
void S01LogPlan(const int idx, S01Plan &plan)
  {
   string side = "FLAT";
   if(plan.dir > 0)
      side = "LONG";
   else if(plan.dir < 0)
      side = "SHORT";
   string text = side + " " + plan.reason;
   if(plan.tradable)
     {
      int digits = (int)SymbolInfoInteger(g_syms[idx].symbol, SYMBOL_DIGITS);
      text = StringFormat("%s lots=%s sl=%s", text,
                          DoubleToString(plan.lots, 2),
                          DoubleToString(plan.sl, digits));
     }
   if(g_syms[idx].last_reason == text)
      return;
   g_syms[idx].last_reason = text;
   Print("Strategy-01 ", g_syms[idx].symbol, " ", text);
  }

//+------------------------------------------------------------------+
bool S01MarginOk(const string symbol, const int dir, const double lots, const double price)
  {
   double margin = 0.0;
   ENUM_ORDER_TYPE kind = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(kind, symbol, lots, price, margin))
      return(false);
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
      return(false);
   return(true);
  }

//+------------------------------------------------------------------+
void S01Send(const int idx, S01Plan &plan)
  {
   string symbol = g_syms[idx].symbol;
   double price = (plan.dir > 0) ? SymbolInfoDouble(symbol, SYMBOL_ASK)
                                 : SymbolInfoDouble(symbol, SYMBOL_BID);
   if(!S01MarginOk(symbol, plan.dir, plan.lots, price))
     {
      plan.tradable = false;
      plan.reason = "MARGIN";
      S01LogPlan(idx, plan);
      return;
     }
   g_pend_r[idx] = plan.r_dist;
   g_pend_until[idx] = TimeCurrent() + 120;
   S01ConfigureFilling(symbol);
   bool sent = false;
   if(plan.dir > 0)
      sent = g_trade.Buy(plan.lots, symbol, 0.0, plan.sl, plan.tp, "S01");
   else
      sent = g_trade.Sell(plan.lots, symbol, 0.0, plan.sl, plan.tp, "S01");
   if(!sent)
     {
      g_pend_r[idx] = 0.0;
      Print("Strategy-01 order failed ", symbol, " ", g_trade.ResultRetcode(),
            " ", g_trade.ResultRetcodeDescription());
      return;
     }
   ulong deal = g_trade.ResultDeal();
   if(deal != 0 && HistoryDealSelect(deal))
     {
      ulong pid = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      if(pid != 0)
         S01GvSet(S01Gv("R", pid), plan.r_dist);
     }
  }

//+------------------------------------------------------------------+
void S01TryEntry(const int idx)
  {
   if(g_halt || idx < 0 || idx >= g_count || !g_syms[idx].active)
      return;
   string symbol = g_syms[idx].symbol;
   datetime bar = iTime(symbol, PERIOD_M5, 0);
   if(bar <= 0)
      return;
   if(bar == g_syms[idx].last_m5)
      return;

   datetime now = TimeCurrent();
   int gap = g_s01_profiles[g_syms[idx].profile].scan_flat_min * 60;
   if(gap < 60)
      gap = 60;
   if(g_syms[idx].last_eval != 0 && (now - g_syms[idx].last_eval) < (gap - 5))
     {
      g_syms[idx].last_m5 = bar;
      return;
     }
   if(g_syms[idx].data_retry > now && g_syms[idx].attempt_bar == bar)
      return;

   int pi = g_syms[idx].profile;
   bool cool = S01InCooldown(symbol, g_s01_profiles[pi].cooldown_min);
   bool has = S01SymbolHasPosition(symbol);
   S01Plan plan;
   S01Decide(g_syms[idx], g_week_kill, cool, has, plan);
   if(plan.reason == "NO_DATA")
     {
      g_syms[idx].attempt_bar = bar;
      g_syms[idx].data_retry = now + 5;
      S01LogPlan(idx, plan);
      return;
     }

   g_syms[idx].last_m5 = bar;
   g_syms[idx].last_eval = now;
   S01LogPlan(idx, plan);
   if(!plan.tradable)
      return;
   if(!InpEnableEntries)
      return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      Print("Strategy-01 ", symbol, " TRADE_DISABLED");
      return;
     }
   if(g_syms[idx].sent_bar == bar)
      return;
   g_syms[idx].sent_bar = bar;
   S01Send(idx, plan);
  }

//+------------------------------------------------------------------+
string S01StatusText()
  {
   string text = "Strategy-01 DEMO\n";
   if(g_halt)
      text += "停手 " + g_halt_why + "\n";
   text += "帳戶 " + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   text += "  " + AccountInfoString(ACCOUNT_CURRENCY) + "\n";
   text += StringFormat("週 %+.2f%%  參考 %s\n", g_week_dd, DoubleToString(g_week_ref, 2));
   if(g_week_kill)
      text += "週熔斷 停新開\n";
   if(!InpEnableEntries)
      text += "新開倉＝關\n";
   for(int i = 0; i < g_count; i++)
     {
      string why = g_syms[i].last_reason;
      if(StringLen(why) == 0)
         why = "等待";
      text += g_syms[i].symbol + " " + why + "\n";
     }
   return(text);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   string bad = S01ValidateInputs();
   if(StringLen(bad) > 0)
     {
      Print("Strategy-01 bad input: ", bad);
      return(INIT_PARAMETERS_INCORRECT);
     }

   string why;
   if(!S01AccountOk(why))
     {
      S01AlertHalt(why);
      return(INIT_FAILED);
     }

   S01ProfilesInit();
   if(!S01BuildSymbols())
      return(INIT_FAILED);

   int alive = 0;
   for(int i = 0; i < g_count; i++)
     {
      if(!S01CreateIndicators(g_syms[i]))
        {
         Print("Strategy-01 indicators failed for ", g_syms[i].symbol);
         S01ReleaseSym(g_syms[i]);
         g_syms[i].active = false;
         g_syms[i].last_reason = "NO_DATA";
         continue;
        }
      alive++;
     }
   if(alive == 0)
     {
      Print("Strategy-01 no indicators created");
      return(INIT_FAILED);
     }

   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   if(cur != "USD" && !g_currency_warned)
     {
      Print("Strategy-01 warning: account currency is ", cur,
            ". Rung locks are in account currency.");
      g_currency_warned = true;
     }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpDeviationPoints);
   g_trade.SetAsyncMode(false);

   for(int i = 0; i < S01_COUNT; i++)
     {
      g_pend_r[i] = 0.0;
      g_pend_until[i] = 0;
     }
   S01UpdateWeek();
   S01SyncSeen();
   EventSetTimer(60);
   string names = "";
   for(int i = 0; i < g_count; i++)
     {
      if(!g_syms[i].active)
         continue;
      if(StringLen(names) > 0)
         names += ",";
      names += g_syms[i].symbol;
     }
   Print("Strategy-01 DEMO ready. login=", AccountInfoInteger(ACCOUNT_LOGIN),
         " symbols=", names, " magic=", InpMagic,
         ". Real accounts are refused.");
   Comment(S01StatusText());
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < S01_COUNT; i++)
      S01ReleaseSym(g_syms[i]);
   Comment("");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_halt)
      return;
   if(PositionsTotal() > 0)
      S01ManagePositions();
   if(!InpChartOnly)
     {
      for(int i = 0; i < g_count; i++)
        {
         if(g_syms[i].symbol == _Symbol)
            S01TryEntry(i);
        }
     }
   else if(g_count > 0)
      S01TryEntry(0);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   S01RefreshHalt();
   if(g_halt)
     {
      Comment(S01StatusText());
      return;
     }
   S01UpdateWeek();
   S01ManagePositions();
   S01SyncSeen();
   for(int i = 0; i < g_count; i++)
     {
      if(g_syms[i].active)
         S01TryEntry(i);
     }
   Comment(S01StatusText());
  }

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   S01OnDeal(trans.deal);
  }

//+------------------------------------------------------------------+
