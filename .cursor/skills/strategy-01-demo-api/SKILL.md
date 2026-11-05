---
name: Strategy-01 DEMO API 操盤
description: >-
  接手 Pepperstone cTrader DEMO Strategy-01：訊號、Kelly／ATR 風控、USD 鎖利、筆記簿 Open API
  全流程。約定 env 路徑已存在則零填寫；只 DEMO、永不 Live。
---
# Strategy-01 DEMO API 操盤

給另一個 Grok Bot **一接手就能用**。細節來源：`/workspace/strategy01-live/` 交接檔＋`compute_signals.py`＋筆記簿 Open API client。**唔發明規則。Token 永不入 git／chat／本 skill 正文。**

## 零填寫前提

接手 bot **唔使再問用戶貼 token**，只要：

1. 可連 `demo.ctraderapi.com:5036` 嘅 Windows `machineId`（Linux box 通常擋 5036）。
2. 本機已有 env 檔（只讀）：`%LOCALAPPDATA%\Temp\ctrader-demo-secure\ctrader-openapi-46950-demo.env`  
   （變數名：`CTRADER_CLIENT_ID`／`SECRET`／`ACCESS_TOKEN`／`REFRESH_TOKEN`／`ACCOUNT_ID=5360748`／`HOST=demo.ctraderapi.com`）
3. Client 已 checkout：`…\Projects\quant-toolkit\projects\ctrader-demo-client`
4. Runner：`.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py`（同機執行副本亦可放 `%LOCALAPPDATA%\Temp\ctrader-demo-secure\run_ctrader_demo.py`；load 上面 env 再轉發 `python -m ctrader_demo …`）

若 env **唔存在**：向已批准持有副本嘅 bot／用戶 **Copy／vault 交檔到上述路徑**，仍然 **唔** 把內容寫入倉庫或聊天。檔到位後即零填寫繼續。

## 範圍（硬）

1. 只 DEMO；預設帳戶 `5360748`。Live `1401957` → 停並通報。
2. 唔代聯絡券商、唔繞過合規、唔把秘密寫入聊天／skill／repo。
3. 時區 Asia/Hong_Kong。
4. 通報：新開、鎖利升檔、平倉、週 −5%、登出／錯戶；用戶沒問可不回。
5. 回報格式：`品種 空／好：±浮盈`（唔加「倉」、唔講 SL／手數）。廣東話繁體極簡。

## 目錄

| 路徑 | 用途 |
|------|------|
| `/workspace/strategy01-live/` | 策略、訊號、日誌、HANDOFF |
| `…/compute_signals.py` | 出 `OPEN_*`／`WAIT`；唔下單 |
| `…/signals_latest.*`、`account_latest.json`、`run_journal.ndjson` | 訊號／快照／日誌 |
| `…/HANDOFF_STRATEGY_PACK.md` | 策略全文 |
| `…/HANDOFF_BRIDGE_OPS.md` | 舊網頁橋（備援） |
| repo `projects/ctrader-demo-client` | Open API CLI |
| `.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py` | Runner：只讀約定 env，再轉發 CLI；檔內零秘密 |

宇宙：XAUUSD、BTCUSD、EURUSD、USDJPY、USDCAD、NAS100、US500、JPN225。

## Open API CLI

```
.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py read-positions
.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py amend-sl --position-id <id> --stop-loss <價>
.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py open-market --symbol-id <id> --side BUY|SELL --volume <api量> [--stop-loss] [--take-profit]
.cursor/skills/strategy-01-demo-api/run_ctrader_demo.py close-position --position-id <id> [--volume]
```

stdout 一行 JSON；code `0`／`1`／`2`（DEMO_GUARD）。`volume ≈ lots×10000`（1000＝10.00 units）。已知 symbolId：XAUUSD=41、JPN225=10006。**開／平／改／讀全部 API，唔用網頁。**

## 策略摘要（全文見 HANDOFF_STRATEGY_PACK）

- 進場：M30+M15 同向，M5 回撤；muse squeeze／chop 閘；核價 ≤0.5×SL、實際 SL≥80% 訊號距。
- 風險：≤ min(¼Kelly, 品種 risk_frac, 1%)×權益；E=1.5×ATR14_M30，EURUSD F=2.0×；放寬 SL 只縮手数。
- 鎖利：+50 早檔，之後每 +100；鎖 ≥ rung−30；跳最高檔；R trail 取較緊；SL 永不放寬。
- 短倉：`SL=entry−(rung−30)/(lots×usd_per)`；JPN225 usd_per≈1。
- 週 −5% ON；日熔斷預設 OFF。`IGNORE_OPEN_BLOCKS`／`ALL_DAY_OPEN` 跟當前腳本＋用戶核准。

## 每輪

1. `read-positions` 核 DEMO。2. 有倉先 `amend-sl`。3. `OPEN_*` → `open-market`。4. 該平 → `close-position`。5. 事後寫 journal。6. 僅規定事件通報。
有倉浮盈≥+50：≤1 分鐘重掃；API 卡>30s 重試最多 2 次。

## 接手 60 秒檢查

1. machineId 可連 demo API。2. env＋runner＋client 路徑存在。3. `read-positions` → code=0。4. 例程 `@every 5m` 指向本 skill。5. 無變化安靜。
