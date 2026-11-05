---
name: Strategy-01 DEMO API 操盤
description: >-
  接手 Pepperstone cTrader DEMO Strategy-01：訊號腳本、Kelly／ATR 風控、USD 階梯鎖利、以及筆記簿 Open
  API 全流程（讀倉／改 SL／市價開／平）。只 DEMO、永不 Live。
---
# Strategy-01 DEMO API 操盤

給另一個 Grok Bot 接手同一套 DEMO 系統用。細節來源：`/workspace/strategy01-live/HANDOFF_STRATEGY_PACK.md`、`HANDOFF_BRIDGE_OPS.md`、`compute_signals.py`，以及 2026-11-06 已切嘅 Open API 主路徑。**唔發明規則。**

**零填寫前提＝env 檔已在約定路徑** `%LOCALAPPDATA%\Temp\ctrader-demo-secure\ctrader-openapi-46950-demo.env`。檔已在該路徑就直接跑，無需填寫任何 token；檔不在就向持有 env 嘅 bot／用戶要已批准副本。ACCESS／REFRESH／CLIENT_SECRET／任何 token 永不寫入 git、PR、本 skill、README 或示範 .env。

## 範圍（硬）

1. **只 DEMO**；帳戶預設 `5360748`（可改，但唔好寫 Live）。Live 預設 `1401957` → 見到即停並通報。
2. 唔代用戶聯絡券商、唔繞過合規擋、唔把 Client Secret／token 寫入聊天或 skill 正文。
3. 時區：Asia/Hong_Kong。
4. 通報只限：新開倉、鎖利升檔、平倉、週 −5% 熔斷、登出／錯戶；用戶沒問可不回。
5. 持倉回報格式（用戶定）：`品種 空／好：±浮盈`（唔加「倉」、唔講止損價同手數）。語言：廣東話繁體極簡。

## 目錄地圖

| 路徑 | 用途 |
|------|------|
| `/workspace/strategy01-live/` | 策略、訊號、日誌、交接檔 |
| `…/compute_signals.py` | 出 `OPEN_*`／`WAIT`；**唔下單** |
| `…/signals_latest.json`／`.md` | 最新訊號 |
| `…/account_latest.json`／`run_journal.ndjson` | 快照／日誌（可能滯後） |
| `…/HANDOFF_STRATEGY_PACK.md` | 策略硬規則全文 |
| `…/HANDOFF_BRIDGE_OPS.md` | 舊網頁橋＋備援說明 |
| `.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py` | Runner 範本：只讀約定 env，再轉發 CLI。檔內零秘密 |

宇宙：`XAUUSD`、`BTCUSD`、`EURUSD`、`USDJPY`、`USDCAD`、`NAS100`、`US500`、`JPN225`。

## 主路徑（2026-11-06 起・Open API）

Linux box **擋** `demo.ctraderapi.com:5036`，必須喺可連線嘅 Windows 筆記簿跑（用該機 `machineId`）。

### 憑證（唔寫入本 skill）

零填寫前提＝env 檔已在約定路徑。接手 bot **唔使填**任何 token，亦唔好問用戶把 token 貼落聊天。

- 約定路徑（寫死）：`%LOCALAPPDATA%\Temp\ctrader-demo-secure\ctrader-openapi-46950-demo.env`
- 變數（只存在於該本機檔，唔存在於 git）：`CTRADER_CLIENT_ID`／`SECRET`／`ACCESS_TOKEN`／`REFRESH_TOKEN`／`ACCOUNT_ID=5360748`／`HOST=demo.ctraderapi.com`
- **檔已在路徑：** 直接跑下面 runner。零填寫、零提示、零示範 .env。
- **檔不在：** 停。向持有 env 嘅 bot／用戶索取**已批准副本**，放到約定路徑。接手 bot 若已有批准嘅 vault／Copy 路徑，只可用 `CTRADER_DEMO_ENV_FILE` 指向該**現成檔**（路徑，唔係 secret 本身）。仍然唔把 ACCESS／REFRESH／CLIENT_SECRET／任何 token 寫入 git、PR、SKILL、README、示範 .env 或聊天。
- 交 env 前必須用戶原話／選項卡批准；權限 只讀 ACL。本 skill 同 runner 唔包含秘密。

### Client

- Repo：`calidadtan-tan/quant-toolkit` → `projects/ctrader-demo-client`（PR 開倉／平倉／改 SL）
- 範例路徑：`C:\Users\<user>\Projects\quant-toolkit\projects\ctrader-demo-client`
- Python：本機 3.12+（範例 arm64 路徑睇接手 bot 記憶）
- Runner 範本（repo，零秘密）：`.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py`
- 本機執行副本（可選，內容與範本相同，仍然零秘密）：`%LOCALAPPDATA%\Temp\ctrader-demo-secure\run_ctrader_demo.py`
- Runner 只 load 約定 env 路徑（或 `CTRADER_DEMO_ENV_FILE` 指向嘅已批准副本），然後轉發 argv 去 `python -m ctrader_demo`。唔會讀命令列上的 token，亦唔會寫 env 檔。

### CLI（stdout 一行 JSON；code `0` 成功／`1` 設定或 API／`2` DEMO_GUARD）

先經 runner（自動讀已存在嘅 env，唔使填 token）：

```
python .cursor/skills/strategy-01-demo-api/run_ctrader_demo.py --check
python .cursor/skills/strategy-01-demo-api/run_ctrader_demo.py read-positions
python .cursor/skills/strategy-01-demo-api/run_ctrader_demo.py amend-sl --position-id <id> --stop-loss <價> [--take-profit <價>]
python .cursor/skills/strategy-01-demo-api/run_ctrader_demo.py open-market --symbol-id <id> --side BUY|SELL --volume <api量> [--stop-loss] [--take-profit] [--label]
python .cursor/skills/strategy-01-demo-api/run_ctrader_demo.py close-position --position-id <id> [--volume]
```

Runner 轉發嘅模組命令（env 已由 runner 注入之後先算有效）：

```
python -m ctrader_demo read-positions
python -m ctrader_demo amend-sl --position-id <id> --stop-loss <價> [--take-profit <價>]
python -m ctrader_demo open-market --symbol-id <id> --side BUY|SELL --volume <api量> [--stop-loss] [--take-profit] [--label]
python -m ctrader_demo close-position --position-id <id> [--volume]
```

量：`API volume`；`1000 = 10.00 units`；`volume ≈ lots × 10000`（0.11 手→1100；0.7 手→7000）。省略 close `--volume`＝全平。只 MARKET 開倉。

已知 `symbolId`（以實盤為準）：`XAUUSD=41`、`JPN225=10006`；其他先對表或由持倉回傳。

**唔再用瀏覽器開／平／改 SL。** 網頁只係緊急備援。

## 策略硬規則（摘要；全文見 HANDOFF_STRATEGY_PACK）

### 進場

- 制度：M30 主 + M15 必須同向；進場 M5 回撤（`SCALP_M30_M15_M5`、`DEMO_RELAXED`）。
- muse 閘：ATR squeeze 要 M5 N=10 擴張；chop 唔追價。
- 核價：入場偏移 ≤ 0.5×SL；實際 SL 距 ≥ 訊號距 80%。
- 可選開關：`IGNORE_OPEN_BLOCKS`／`ALL_DAY_OPEN` 以當前 `compute_signals.py` 同用戶核准為準。

### 風控與手數

- 單筆風險 ≤ `min(¼Kelly, 品種 risk_frac, 1%) × 權益`，計入佣金＋滑價。
- 止損地板：默認 E=`1.5×ATR14_M30`；EURUSD F=`2.0×`。放寬 SL **只縮手数**，唔放大風險$。
- `lots = floor_to_step(risk_usd / (sl_dist×usd_per + slip + commission))`；平台步長可能係 0.1。

### 鎖利（主出場）

- USD 階梯：峰值淨浮盈 ≥ **+50** 可早檔；其後每 **+100** 一檔；鎖 ≥ `rung−30`；一次跳到已達最高檔。
- 另有品種 R trail；同 USD 檔取 **較緊**。SL **永不放寬**。
- 短倉：`SL = entry − (rung−30)/(lots×usd_per_point)`；多倉反向。JPN225 `usd_per≈1.0`／手／點（以實盤為準）。
- 有倉且浮盈 ≥+50：巡檢 ≤1 分鐘；API 改單卡 >30s → 重試，同目標最多 2 次，仍失敗報用戶同艦隊總經理。

### 熔斷與時段（預設）

- 日熔斷 OFF（DEMO 樣本）；**週 −5% ON**（`week_ref_equity` 以交接／記憶為準）。
- BTC 新倉預設只週末 HKT；指數時段見 `SYMBOL_PROFILES`（若 `IGNORE_OPEN_BLOCKS` 打開則跟腳本）。

## 每輪例程順序

1. `read-positions` 確認 DEMO 帳戶同持倉／浮盈／現 SL／`positionId`。
2. 有倉先算最高 rung → `amend-sl`（目標價寫死）。
3. 跑 `compute_signals.py`；`OPEN_*` 且未持倉 → `open-market`（帶硬 SL）。
4. 該主動平 → `close-position`。
5. 事後寫 `run_journal.ndjson`／`account_latest.json`（先改單後寫檔）。
6. 僅規定事件通報；無變化安靜。

以上全部經 `run_ctrader_demo.py` 呼叫。第一個動作之前唔使填 token。

## 速度

執行為先：該開／鎖／平，第一個動作就 API。唔截圖查倉。浮盈以 API／用戶畫面為準，唔信舊檔。

## 接手檢查清單

1. 零填寫：約定 env 檔已在路徑就直接用。唔在就向持有 env 嘅 bot／用戶要已批准副本，唔好現場填 token，亦唔好寫入 git。確認可連 `demo.ctraderapi.com:5036` 嘅 machineId；runner／client 路徑可用。
2. 煙測：`run_ctrader_demo.py --check`，然後 `read-positions` → `code=0`、`traderLogin`／`accountId`＝DEMO。
3. 讀 `HANDOFF_STRATEGY_PACK.md` + 當前 `compute_signals.py` 開關。
4. 建／改例程：每 ≥5 分鐘；有倉輪內每分鐘重掃鎖利；prompt 指向本 skill 同上述路徑。
5. 回報格式同語言跟用戶偏好；Token 永不入 chat。

## 唔做

Live、攤平、同向加倉、放寬 SL、例行截圖、把秘密貼出嚟、未批准就交 env、喺 repo 放示範 .env 或任何 token。
