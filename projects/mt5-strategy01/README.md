# Strategy-01 DEMO（MT5 Expert Advisor）

**只限 DEMO。不要把這個 EA 掛到真實帳戶。**

真實帳戶（`ACCOUNT_TRADE_MODE_REAL`）會在初始化時直接拒絕。預設也會拒絕交接包裡的 Live 帳戶號碼。沒有「允許 Live」的開關。改源碼才能繞過，請不要這樣做。

這不是投資建議，也不是 Live 規格。它把 Strategy-01 DEMO 的進場、硬止損、Kelly 式風險上限同美元鎖利，寫成可以在 MetaTrader 5 編譯的 EA。cTrader Open API 那條路不在這裡，倉庫裡也沒有任何 API token、密碼或 client secret。

## 這個 EA 做什麼

| 項目 | 行為 |
| --- | --- |
| 制度 | M30 為主，M15 必須同向。H1 不用 |
| 進場 | M5 回撤（DEMO 放寬預設）。可選 squeeze 擴張 |
| 止損 | 每一筆新單都帶伺服器硬止損。沒有止損的本策略持倉會先補回，補不了就平掉 |
| 手數 | `min(品種 risk_frac, ¼Kelly 若為正, ¼f*, 1%) × 權益`，再扣滑價同佣金緩衝，向下取到手數步長 |
| 止損地板 | 非 EURUSD 用 **E = 1.5 × M30 ATR14**；EURUSD 用 **F = 2.0 × M30 ATR14**。地板只會把止損放寬，手數跟著縮小 |
| 加倉 | 不做。同一品種已有任何持倉（含手動單）就不再開。也不做攤平、金字塔、對沖加碼 |
| 鎖利 | 峰值淨浮盈先到 **+50**，其後每 **+100**（50、150、250…）。一次跳到已達到的最高檔，鎖定目標 ≥ 檔位 − 30。止損只收緊 |
| R 移動止損 | 預設開啟。峰值淨浮盈達到 +100 之後才跟品種 R 層比較，取比美元檔更緊的那個 |
| 週熔斷 | **−5% 開啟**。觸發後本 HKT 週停止新開倉，已有倉繼續鎖利。日熔斷保持關閉 |
| 時段 | 用 GMT+8 當香港時間。BTC 只許週六、週日新開。NAS100／US500 只許美股時段。JPN225 只許東京時段 |

USDCAD 的 profile 名稱仍是 `mean_revert_fade`（小注、快鎖）。進場仍是趨勢回撤。真正的均值回歸進場沒有做。

## 檔案

| 檔案 | 用途 |
| --- | --- |
| `Strategy01Demo.mq5` | EA 本體。輸入、下單、改止損、通報都在這裡 |
| `Include/S01Common.mqh` | 品種表、時段、風險、階梯、R 層。純規則，不含下單 |
| `Include/S01Engine.mqh` | M30／M15／M5 訊號同手數。必須在輸入宣告之後引入 |
| `tests/test_rules.py` | 階梯、風險、手數、時段、品種表的對照測試。不能代替 MetaEditor 編譯 |
| `README.md` | 本說明 |

## 如何掛上 MT5

1. 在 MetaTrader 5 選 **檔案 → 開啟數據文件夾**。
2. 把整個 `mt5-strategy01` 資料夾複製到 `MQL5/Experts/`。不要只複製 `.mq5`，否則 `Include` 會找不到。
3. 用 MetaEditor 打開 `MQL5/Experts/mt5-strategy01/Strategy01Demo.mq5`，按 **編譯（F7）**。需要較新的 MT5（支援 `input group`，約 build 2615 之後）。
4. 原始碼是 **UTF-8（含 BOM）**。若輸入名稱中文亂碼，在 MetaEditor 另存為 Unicode 再編譯。
5. 把要交易的品種加進市場報價。名稱對不上時，改下面的品種輸入，或填後綴（例如 `.a`、`m`）。
6. 登入的必須是 **DEMO**。把「預期 DEMO 帳戶」改成你自己的 DEMO 號碼。預設 `5360748` 只是交接包裡的例子。
7. 把 EA 拖到任意週期的圖表。計算用的是 M30、M15、M5，圖表週期不影響訊號。
8. 打開「允許演算法交易」。
9. 圖表左上角註釋會顯示帳戶、週回撤，以及每個品種最近一次的原因代碼。

策略測試器請一次只測一個品種，並把「只交易目前圖表」設為 `true`。測試器不會可靠地推動市場報價裡其他品種的逐筆行情。測試器會略過帳戶號碼核對，但仍然拒絕真實帳戶模式。

想先看訊號、不下新單：把「允許新開倉」設為 `false`。已有倉的硬止損同鎖利仍會跑。

## 輸入

標籤是繁體中文，變數名是英文。下面是預設值。

### 帳戶（只限 DEMO）

| 輸入 | 預設 | 意思 |
| --- | --- | --- |
| `InpDemoLogin` | `5360748` | 必須登入這個 DEMO。`0` 表示不核對號碼，但仍拒絕真實帳戶 |
| `InpBlockedLiveLogin` | `1401957` | 見到這個 Live 號碼就停手。`0` 表示不使用黑名單 |
| `InpMagic` | `26010401` | 只管理這個 magic 的倉 |
| `InpChartOnly` | `false` | `true` 時只交易目前圖表（名稱要對得上某個品種） |
| `InpSuffix` | 空 | 接到名稱後面，例如 `.a` 或 `m` |
| `InpEnableEntries` | `true` | `false` 時不開新倉 |

多品種模式會嘗試這些名稱，找不到再試常見別名：`XAUUSD`／`GOLD`，`BTCUSD`／`BTCUSDT`，`NAS100`／`US100`／`USTEC`，`US500`／`SPX500`／`SP500`，`JPN225`／`JP225`。留空該輸入等於在多品種模式停用該品種。

### 風險與手數

| 輸入 | 預設 | 意思 |
| --- | --- | --- |
| `InpRiskFrac` | `0.01` | 再跟品種上限、1% 取較小。`0` 表示不另加這一層 |
| `InpFStar` | `0.126` | 全局 Kelly `f*`。實際再取 `¼f*`。`0` 表示不用這層 |
| `InpGlobalRiskCap` | `0.01` | 硬頂。填大於 1% 也會被夾成 1% |
| `InpAtrFloorE` | `1.5` | **E**。EURUSD 以外，止損距離至少 `E × ATR14(M30)` |
| `InpAtrFloorF` | `2.0` | **F**。只用於 EURUSD |
| `InpLotStep` | `0.01` | 手數步長。若經紀商步長更粗，用經紀商的 |
| `InpMinLot` | `0.01` | 最小手數。再跟品種最小手數取較大 |
| `InpCommissionBufferUsd` | `7.0` | 來回佣金緩衝，USD／手。只加在 EURUSD、USDJPY、USDCAD、XAUUSD |
| `InpWeeklyKillPct` | `-5.0` | 週熔斷。相對參考權益跌到這個百分比就停新開 |
| `InpWeekRefEquity` | `0` | `0`：該 HKT 週第一次運行時記下淨值。正數：用你填的固定參考，不會每週自動換 |
| `InpUseBalance` | `false` | `false` 用淨值計風險，`true` 用餘額 |

品種風險上限（不能被輸入放大）：USDJPY 0.5%，EURUSD 0.6%，USDCAD 0.25%，XAUUSD 0.6%，NAS100 0.4%，US500 0.5%，JPN225 0.8%，BTCUSD 0.6%。Kelly 模擬值為正時，再跟 `¼ × kelly_sim` 取較小。負的 Kelly 不會把風險打成負數，那些品種用已經砍過的 `risk_frac`。

### 進場（DEMO 放寬預設）

| 輸入 | 預設 | 意思 |
| --- | --- | --- |
| `InpPullbackBars` | `24` | M5 回撤回看 |
| `InpNearZoneAtr` | `0.5` | 收盤距 M30 EMA20 在這個倍數以內算近區 |
| `InpChaseHardAtr` | `2.0` | 超過就放棄 |
| `InpChaseSoftAtr` | `1.2` | 只標記。Chop 裡連軟追價也不開 |
| `InpStructureAtrMult` | `1.5` | M5 結構止損倍數 |
| `InpSwingBufferAtr` | `0.1` | 擺動高低點外的緩衝 |
| `InpSlAbandonAtr` | `0.4` | 最終距離仍窄過 `0.4 × M5 ATR` 就放棄 |
| `InpDriftVsSl` | `0.5` | 現價偏離訊號收盤超過 `0.5 × 止損距離` 就放棄 |
| `InpSlKeepFrac` | `0.80` | 實際止損距離至少保留訊號距離的 80%。填 `80` 也可以 |

### Muse 閘

| 輸入 | 預設 | 意思 |
| --- | --- | --- |
| `InpSqueezePct` | `0.20` | M30 ATR14 處於近 60 根的這個分位或更低 → squeeze。填 `20` 也可以 |
| `InpAtrStatsBars` | `60` | 分位同中位數的樣本數 |
| `InpExpandBars` | `10` | squeeze 時，M5 收盤要突破前 N 根高低 |
| `InpChopRatio` | `0.5` | `\|EMA50−EMA200\| / ATR14` 小於此值 → chop |
| `InpRegimeGapAtr` | `0.15` | 兩條 EMA 差距小於此倍數 → 制度關閉 |
| `InpRegimeBoom` | `2.2` | ATR 大於中位數的這個倍數 → 制度關閉 |

### 出場鎖利

| 輸入 | 預設 | 意思 |
| --- | --- | --- |
| `InpRungFirstUsd` | `50` | 第一檔 |
| `InpRungStepUsd` | `100` | 之後每檔加上這個數 |
| `InpRungLockBackUsd` | `30` | 鎖定目標 = 檔位 − 30 |
| `InpUseRTrail` | `true` | 跟美元檔取較緊的止損 |
| `InpRTrailMinPeakUsd` | `100` | 淨浮盈未到這個數，不用 R 層（+50 檔仍可用） |
| `InpHotFloatUsd` | `50` | 達到後，非檔位跳升的改單最多約 2 秒一次；否則約 15 秒 |
| `InpUseFarTp` | `false` | 遠端止盈。不是主出場 |
| `InpFarTpR` | `3.0` | 遠端止盈距離 |

預設階梯是 **+50、+150、+250…**。這跟較舊交接文字（第一檔 +100，然後 +200、+300）不同。若要改回舊階梯，設 `InpRungFirstUsd = 100`、`InpRungStepUsd = 100`。

多單只會把止損上移，空單只會下移。候選價會立刻成交，或會把一筆本來想鎖利的單子打成虧損離場時，維持原來的止損。

帳戶貨幣不是 USD 時，檔位仍用帳戶貨幣計算，不會自動換匯。DEMO 應使用 USD 帳戶。

### 執行

| 輸入 | 預設 | 意思 |
| --- | --- | --- |
| `InpDeviationPoints` | `30` | 市價單允許的滑點，單位是點 |

## 圖表上的原因代碼

沒有變化時，同一代碼不會反覆寫進專家日誌。

| 代碼 | 意思 |
| --- | --- |
| `REGIME_OFF` | M30 制度關閉 |
| `M15_DISAGREE` | M15 沒有同向 |
| `RANGE_SQUEEZE_NO_EXPAND` | 處於 squeeze，但 M5 未突破近 10 根 |
| `CHOP_SKIP` | chop 下追價，或不是清晰回撤 |
| `NO_PULLBACK` | 沒有 EMA／Fib 觸及，也不在近區 |
| `NO_CONFIRM` | 多單收盤未站上 M5 EMA20，或空單未跌破 |
| `CHASE_BLOCKED` | 距離 M30 EMA20 超過硬擋 |
| `OPEN`／`OPEN_CAUTIOUS`／`OPEN_CHASE_SOFT` | 訊號通過。CAUTIOUS 表示在 profile 時段內、但不在首選時段 |
| `PROFILE_SESSION_SKIP` | 現在的時段桶不在該品種 sessions |
| `WEEKDAY_BTC_SKIP` | BTC 平日不開新倉 |
| `OUTSIDE_US_CASH_SKIP` | 指數不在約 22:30–05:00 HKT |
| `OUTSIDE_ASIA_TOKYO_SKIP` | JPN225 不在約 08:00–14:00 HKT |
| `COOLDOWN` | 硬止損之後的冷卻還沒完 |
| `WEEKLY_KILL` | 週 −5% 已觸發 |
| `PRICE_DRIFT` | 現價偏離訊號價太多 |
| `SL_TOO_TIGHT` | 止損距離不成立 |
| `LOTS_ZERO` | 按風險算出來不足最小手數 |
| `HAS_POSITION` | 該品種已有倉 |
| `NO_DATA` | K 線或指標尚未就緒 |
| `MARKET_CLOSED` | 品種現在不能開這個方向 |
| `MARGIN` | 可用保證金不足 |
| `TRADE_DISABLED` | 終端機不允許演算法交易 |

時段桶（HKT）：亞洲 07:00–15:00，倫敦 15:00–21:00，紐約 21:00–07:00。外匯同黃金若落在 profile 允許的時段、但在 15:00–24:00 之外，仍可開倉並標成 CAUTIOUS。指數同 JPN225 沒有這個放寬。

## 通報

只在這些情況用 `Alert`（同時寫入專家日誌）：

- 新開倉：`EURUSD 好：開倉` 或 `EURUSD 空：開倉`
- 鎖利升檔：`EURUSD 鎖利 +150`
- 平倉：`EURUSD 平倉：-12.34`
- 週熔斷：`週熔斷 -5.0% 停新開`
- 錯戶或 Live：`錯戶／Live 停手`
- 斷線：`登出停手`

EA 啟動時已經存在的倉不會被當成新開倉再報一次。週熔斷在同一 HKT 週只報一次；淨值之後回升也不會自動恢復新開倉，要等下一週。

## 跟 cTrader／Open API 路徑的差別

cTrader 那條路是：讀 DEMO 持倉、改止損、市價開倉、平倉，訊號來自獨立的 Python。這個 EA 在 MT5 終端裡自己算、自己下單。沒有網頁、沒有 Open API、沒有 token 檔。

下面這些是近似，不是逐行移植：

| 項目 | 這裡怎麼做 |
| --- | --- |
| 清晰回撤 | 近 24 根 M5 有 K 線碰到 M30 EMA20，或較新的 K 線刺入 38.2%–61.8% 回撤區。不是原 Python 的完整型態庫 |
| Squeeze／chop | 用經紀商 M30 的 ATR14 分位同 EMA 距離。沒有獨立的 muse 模型 |
| 合約規格 | 用 `OrderCalcProfit` 讀經紀商的點值。不再假設指數「1 點 = 1 美元」或固定的黃金合約 |
| 佣金 | 輸入的來回緩衝，不是經紀商佣金表。淨浮盈 = 持倉盈虧 + 掉期 − 緩衝 × 手數（整段來回，偏保守） |
| 鎖利價 | 目標淨利包含這筆緩衝，所以會比「只寫 `(檔位−30)/(手數×每點價值)`」略緊 |
| 階梯起點 | 預設第一檔 +50，不是舊文的 +100 |
| ATR 地板 | 用 E／F（1.5×／2.0× M30 ATR）取代舊文只給外匯的 0.5× M30 ATR。結構止損仍先用 M5，地板只負責放寬 |
| 時鐘 | 固定 GMT+8。沒有交易所假日曆。美股時段是固定的 22:30–05:00 HKT |
| 掃描 | 計時器每 60 秒管一次持倉；圖表有 tick 時也會管。浮盈高的品種若沒有 tick，最久約 60 秒才看到新高。空倉訊號依各品種 `scan_flat`（多數 5 分鐘，BTC 15 分鐘） |
| 改單頻率 | 止損沒有跳檔時，約 15 秒才改一次；淨浮盈達到熱掃描門檻後約 2 秒。失敗後約 10 秒才重試 |
| 峰值記憶 | 存在本機終端機全域變數，鍵名含 magic 同持倉票號。換電腦或清掉全域變數後，R 軌要等新倉；若重啟時止損仍在虧損側，會用 \|進場價−止損\| 還原 R。美元階梯用重啟後重新累積的峰值 |
| 測試器 | 多品種掃描不可靠。請單圖、單品種 |
| 沒有做 | 金字塔、跨品種配對、訂單流、Dual Thrust 當主進場、BB／RSI 逆勢、日熔斷、1.5R 部分平倉、USDCAD 真正均值回歸進場 |

訊號只用已收盤的 K 線。持倉管理用即時買價／賣價，以及開倉之後才開始的當前 M1 高低，避免兩次檢查之間的尖峰完全消失。

## 安全

- 倉庫和這個資料夾沒有 cTrader client id、secret、access token、refresh token。
- 預設帳戶號碼只是 DEMO／Live 的識別例子，用來擋錯戶。請改成你自己的 DEMO。
- 登出或帳戶切換後，EA 會停手。切回正確的 DEMO 才會繼續。
- 週參考權益存在終端機全域變數。那是本機狀態，不是密鑰。

## 在本機核對規則數字

沒有安裝 MetaEditor 的環境可以先跑：

```bash
python3 projects/mt5-strategy01/tests/test_rules.py
```

這只核對階梯、風險、手數、時段、品種表同括號平衡。真正能否編譯，仍要在 MetaEditor 按 F7。
