# cTrader Open API DEMO 客戶端

這是一個最小的 **DEMO 限定** cTrader Open API 客戶端，只做三件事：

1. 以應用程式憑證與帳戶權杖完成授權。
2. 讀取 DEMO 帳戶 `5360748` 的未平倉持倉與浮動損益。
3. 用 `ProtoOAAmendPositionSLTPReq`（payloadType `2110`）修改該持倉的停損／停利。

交易連線使用官方 JSON WebSocket（說明書的 [Send and receive JSON](https://help.ctrader.com/open-api/sending-receiving-json/)），位址寫死為 `wss://demo.ctraderapi.com:5036`。沒有第三方套件。

官方文件入口：<https://help.ctrader.com/open-api/>

## 應用程式狀態（現在還不能換權杖）

Open API 應用程式名稱是 **poteto-demo-sltp**。Spotware 上的狀態是 **Submitted**，不是 **Active**。

在 Spotware 把狀態改成 Active 之前：

- OAuth 不會發出授權碼。
- `CTRADER_ACCESS_TOKEN` 與 `CTRADER_REFRESH_TOKEN` 必須留空。
- 不要把 Client ID、Client Secret 或權杖寫進程式碼，也不要提交 `.env`。

啟用之後，再照下面的「授權並取得權杖」完成 OAuth。在那之前，用單元測試的假連線確認訊息形狀即可。本目錄沒有、也不該宣稱已經呼叫過 Spotware。

## 量化交易 bot 呼叫方式

在 `projects/ctrader-demo-client` 目錄執行。兩種入口回傳同一份報告。

命令：

```bash
python3 -m ctrader_demo read-positions
python3 -m ctrader_demo amend-sl --position-id 123456789 --stop-loss 1.08000 --take-profit 1.12000
```

程式進入點（不印出，直接回傳 dict）：

```python
from ctrader_demo import read_positions, amend_sltp

report = read_positions()
report = amend_sltp(123456789, stop_loss=1.08, take_profit=1.12)
```

`ctrader_demo.cli:main` 與 `python3 -m ctrader_demo` 相同。成功時 stdout 是一行 JSON，stderr 為空。失敗時 stdout 與 stderr 是同一行 JSON。bot 解析 `code` 與 `message` 即可。

成功：

```json
{"code":0,"command":"read-positions","error":null,"message":"ok","ok":true,"result":{}}
```

失敗（live 主機或其他帳戶；此時還沒有交易請求）：

```json
{"code":2,"command":"read-positions","error":"DEMO_GUARD","message":"DEMO GUARD: refusing host 'live.ctraderapi.com'. ...","ok":false}
```

| `code` | `error` | 意義 |
| --- | --- | --- |
| 0 | `null` | 成功。持倉與損益在 `result` |
| 1 | `CONFIG` / `API` / `USAGE` / `INTERNAL` | 設定不足、參數錯誤，或代理回傳錯誤。不代表改單已成功 |
| 2 | `DEMO_GUARD` | 主機不是 `demo.ctraderapi.com`，或帳戶不是 `5360748`。請求沒有送出 |

## 硬性限制

程式在送出任何交易請求之前就會檢查。不符合就結束，結束代碼是 `2`，且不會建立交易連線。

| 限制 | 行為 |
| --- | --- |
| 交易主機只能是 `demo.ctraderapi.com` | `CTRADER_HOST` 空白時用這個主機。設成別的值（包含 `live.ctraderapi.com`、`live1.p.ctrader.com`）立刻拒絕。 |
| 連接埠只能是 `5036` | 這是 JSON 埠。Protobuf 的 `5035` 與任何 live 埠都會拒絕。 |
| 登入號只能是 `5360748` | `CTRADER_ACCOUNT_ID` 是 cTrader 畫面登入號（`traderLogin`），不是 `ctidTraderAccountId`。缺失或不等於 `5360748` 就拒絕。 |
| 只使用解析出的 ctid | 帳戶清單裡 `traderLogin == 5360748` 的那一筆提供 `ctidTraderAccountId`（實測與登入號不同，例如 `49216463`）。後續授權、讀倉、改停損只用這個 ctid。其他 ctid，即使數字剛好是 `5360748`，也不送。 |
| 帳戶不得標成 Live | 該筆 `isLive` 為 true 時，在 `ProtoOAAccountAuthReq` 之前停止。 |
| 不送出其他交易指令 | 允許的 `payloadType` 只有應用程式授權 `2100`、帳戶清單 `2149`、帳戶授權 `2102`、持倉對帳 `2124`、浮動損益 `2187`、修改停損停利 `2110`。新單、平倉、改掛單都會在寫入 socket 之前被拒絕。 |
| 只讀權限不能改停損 | `permissionScope` 為 `SCOPE_VIEW` / `accounts` 時，不送 `2110`。 |
| 秘密不進版本庫 | 憑證只從環境變數或 gitignore 的 `.env` 讀取。 |

OAuth 權杖交換使用固定網址 `https://openapi.ctrader.com/apps/token`。這是授權服務，不是交易主機，程式不接受改寫，也不跟隨重新導向。授權頁在 `https://id.ctrader.com/`。這兩個網址都不會下單。

## 註冊 Spotware Open API 應用程式

1. 建立或登入 cTrader ID：<https://id.ctrader.com>
2. 打開 Open API 應用程式頁：<https://openapi.ctrader.com/apps>
3. 建立一個應用程式。
4. 在 Credentials 欄按 View，取得 **Client ID** 與 **Client Secret**。
5. 編輯應用程式，在 Redirect URIs 新增一個你控制的網址，例如 `https://localhost`。說明書提到第一個 redirect URI 是 Playground 用的，請另外新增自己的網址後按 Save。
6. 修改停損停利需要 **trading** 範圍。`accounts` 只能讀帳戶資料。

文件：

- 授權流程：<https://help.ctrader.com/open-api/account-authentication/>
- 端點：<https://help.ctrader.com/open-api/proxies-endpoints/>
- 訊息：<https://help.ctrader.com/open-api/messages/>
- 損益：<https://help.ctrader.com/open-api/profit-loss-calculation/>
- Proto 定義：<https://github.com/spotware/openapi-proto-messages>

## 授權並取得權杖

在 `projects/ctrader-demo-client` 目錄：

```bash
cp .env.example .env
```

應用程式啟用之後，在 `.env` 填上 `CTRADER_CLIENT_ID`、`CTRADER_CLIENT_SECRET`，並保持：

```text
CTRADER_HOST=demo.ctraderapi.com
CTRADER_ACCOUNT_ID=5360748
CTRADER_REDIRECT_URI=https://localhost
```

JSON 連接埠固定是 `5036`，沒有對應的環境變數。

印出授權網址：

```bash
python3 -m ctrader_demo auth-url --redirect-uri 'https://localhost'
```

或自行打開（`scope` 請用 `trading`）：

```text
https://id.ctrader.com/my/settings/openapi/grantingaccess/?client_id={CTRADER_CLIENT_ID}&redirect_uri=https://localhost&scope=trading&product=web
```

登入 cTrader ID，按 Allow access。瀏覽器會導回：

```text
https://localhost/?code=一次性授權碼
```

授權碼大約 **60 秒**內失效。立刻換成 access token 與 refresh token：

```bash
python3 -m ctrader_demo exchange-code --code '貼上的code' --redirect-uri 'https://localhost'
```

把輸出的 `accessToken`、`refreshToken` 寫進 `.env` 的 `CTRADER_ACCESS_TOKEN`、`CTRADER_REFRESH_TOKEN`。不要提交 `.env`，也不要寫進程式碼。

Access token 約 2,628,000 秒（約 30 天）後過期。Refresh token 本身不過期，但每次刷新都會使舊的一對失效：

```bash
python3 -m ctrader_demo refresh-token
```

請改用新印出的兩個權杖。

### 用 Playground 取得自己的權杖

在 Applications 頁按 Playground，範圍選 **trading**，再按 Get token。把畫面上的 access token 與 refresh token 放進 `.env`。這只適合你自己的 cTID 做 DEMO 開發。

此客戶端仍只接受 DEMO 登入號 `5360748`。權杖的帳戶清單裡必須有 `traderLogin == 5360748` 且 `isLive` 不是 true 的一筆。程式用那一筆的 `ctidTraderAccountId` 送後續請求。清單裡的其他帳戶不會被使用。`49216463` 只是曾經觀察到的 ctid 範例，不是寫死的第二個允許值。

## 環境變數

| 變數 | 必填 | 說明 |
| --- | --- | --- |
| `CTRADER_CLIENT_ID` | 交易與換權杖時必填 | 應用程式 Client ID。啟用前留空，不要寫進程式 |
| `CTRADER_CLIENT_SECRET` | 交易與換權杖時必填 | 應用程式 Client Secret。同上 |
| `CTRADER_ACCESS_TOKEN` | 讀持倉、改停損時必填 | OAuth access token。Submitted 期間不存在 |
| `CTRADER_REFRESH_TOKEN` | 只在 `refresh-token` 必填 | OAuth refresh token。Submitted 期間不存在 |
| `CTRADER_ACCOUNT_ID` | 永遠必填 | DEMO 登入號 `traderLogin`，只能是 `5360748`。不是 `ctidTraderAccountId` |
| `CTRADER_HOST` | 否 | 省略時為 `demo.ctraderapi.com`。其他值會被拒絕 |
| `CTRADER_REDIRECT_URI` | 否 | 省略時為 `https://localhost`。其他值會被拒絕 |

已存在的環境變數優先於 `.env`。`.env` 只填補尚未設定的名稱。

## 讀取持倉與浮動損益

```bash
cd projects/ctrader-demo-client
python3 -m ctrader_demo read-positions
```

流程是：

1. `ProtoOAApplicationAuthReq`（2100）
2. `ProtoOAGetAccountListByAccessTokenReq`（2149），找到 `traderLogin == 5360748` 且不是 Live，記下該筆 `ctidTraderAccountId`
3. `ProtoOAAccountAuthReq`（2102），`ctidTraderAccountId` 用上一步解析出的值，不是 `5360748`
4. `ProtoOAReconcileReq`（2124），`returnProtectionOrders` 為 false，停損停利取自持倉本身
5. `ProtoOAGetPositionUnrealizedPnLReq`（2187）

只輸出 `POSITION_STATUS_OPEN` 的持倉。已平倉與掛單建立的空持倉不會列入。

欄位換算：

- `volume` 是協定原值。文件定義 1000 表示 10.00 單位。`volumeUnits` 是除以 100 後的十進位字串。
- `swap`、`commission`、`usedMargin` 依該持倉的 `moneyDigits`，以 `原值 / 10^moneyDigits` 換算，單位是帳戶入金貨幣。
- `grossUnrealizedPnL` 與 `netUnrealizedPnL` 依損益回應的 `moneyDigits` 換算。官方定義：`netUnrealizedPnL` **不含**預估平倉手續費。
- `entryPrice`、`stopLoss`、`takeProfit` 已是絕對價格，不再縮放。

沒有 `moneyDigits` 時不會猜一個位數，程式會報錯，避免把整數原值誤當成貨幣金額。

## 修改停損／停利

至少要給一個價格。價格是絕對價，例如 `1.23456`。省略的那一個不會出現在請求裡，由伺服器保留原值。

```bash
python3 -m ctrader_demo amend-sl --position-id 123456789 --stop-loss 1.08000 --take-profit 1.12000
```

只改停損：

```bash
python3 -m ctrader_demo amend-sl --position-id 123456789 --stop-loss 1.08000
```

送出的 JSON 形狀。`ctidTraderAccountId` 是帳戶清單解析出的值；下面的 `49216463` 只是實測範例，不是寫死的允許清單：

```json
{
  "clientMsgId": "<uuid>",
  "payloadType": 2110,
  "payload": {
    "ctidTraderAccountId": 49216463,
    "positionId": 123456789,
    "stopLoss": 1.08,
    "takeProfit": 1.12
  }
}
```

成功時，代理回 `ProtoOAExecutionEvent`（2126）。`ORDER_REJECTED`、`ORDER_CANCEL_REJECTED` 或帶 `errorCode` 的事件會以結束代碼 `1` 失敗，不會被印成成功。`ProtoOAErrorRes`（2142）與 `ProtoOAOrderErrorEvent`（2132）同樣是失敗。

這個指令只改既有持倉的停損停利。它不能開新倉，也不能平倉。

## 在 DEMO 平台上核對

這些步驟需要你自己的 DEMO 登入與上面的憑證。本儲存庫的單元測試使用假連線，**沒有**替你呼叫 Spotware。

1. 用 cTrader Web 或桌面版進入 **DEMO**（不是 Live）。確認帳戶識別碼是 `5360748`。
2. 執行 `read-positions`。對照 `positionId`、方向、`volumeUnits`、進場價、停損、停利。
3. 把畫面上的浮動損益和 `grossUnrealizedPnL`、`netUnrealizedPnL` 比較。報價在兩次請求之間可能略有變動。`net` 不含預估平倉手續費，所以可能和畫面上的數字差一個手續費。
4. 選一筆 DEMO 持倉，用 `amend-sl` 改成一個離市價夠遠、符合該商品規則的停損或停利。
5. 回到 cTrader 重新整理該持倉，確認 Stop Loss / Take Profit 已改變。
6. 不要對 Live 帳戶做這件事。若把 `CTRADER_HOST` 改掉，或把 `CTRADER_ACCOUNT_ID` 改成別的數字，程式會以代碼 `2` 結束，而且不會送出交易請求。應用程式仍是 Submitted 時，這一步要等 Active 與 OAuth 完成後才能在平台上核對。

## 結束代碼

程序的結束代碼等於報告裡的 `code`。stdout 永遠是一行 JSON。失敗時 stderr 是同一行，方便另一個 bot 只讀 stderr。權杖與 client secret 若出現在 `message` 裡會被換成 `***`。

| `code` | 意義 |
| --- | --- |
| 0 | 指令完成。`result` 是持倉或改單結果 |
| 1 | 設定不足、參數錯誤，或代理回傳錯誤。不代表交易已經成功 |
| 2 | DEMO 防護拒絕（主機、帳戶、Live 旗標、view-only 卻要改停損）。交易請求沒有送出 |

## 測試

在 `projects/ctrader-demo-client`：

```bash
python3 -m unittest discover -s tests -t . -v
```

測試檢查訊息形狀、金額縮放、授權順序，以及防護會在 `socket.create_connection` 之前返回。測試沒有連上 `demo.ctraderapi.com`。poteto-demo-sltp 仍是 Submitted，沒有權杖，不能也不應宣稱 API 呼叫已經成功。

## 為什麼不用 OpenApiPy

Spotware 的官方 Python SDK 是 [OpenApiPy](https://github.com/spotware/OpenApiPy)。它依賴 Twisted，範例還包含 live 主機切換。Open API 同時定義了 JSON（連接埠 5036）。這個目錄用標準庫實作 JSON WebSocket，把允許送出的 payloadType 寫死，假傳輸就可以測完整個授權與改單順序，也不會出現一條通往 live 的連線參數。

訊息名稱與編號仍是官方 `ProtoOA*` 契約，對照 `openapi-proto-messages`。

## 仍須由你提供的憑證

程式庫不包含、也不會提交下列秘密。poteto-demo-sltp 仍是 Submitted，所以現在這些權杖還不存在，要等 Spotware 把應用程式設為 Active 之後才能做 OAuth：

- `CTRADER_CLIENT_ID`
- `CTRADER_CLIENT_SECRET`
- `CTRADER_ACCESS_TOKEN`
- `CTRADER_REFRESH_TOKEN`（刷新時需要；第一次可用授權碼交換）

`CTRADER_ACCOUNT_ID` 必須維持 `5360748`（DEMO 登入號 `traderLogin`）。`CTRADER_HOST` 必須是 `demo.ctraderapi.com`。`CTRADER_REDIRECT_URI` 必須是 `https://localhost`。Open API 的 `ctidTraderAccountId` 由帳戶清單解析，不要把它填成 `5360748`。
