# Từ 0 đến Hero — Giao dịch Binance Futures Testnet trong Sagittarius Elite Warrior

> **Đối tượng:** tech lead / dev chưa từng làm việc với sàn crypto, cần hiểu **toàn bộ** tính năng
> giao dịch testnet của app này: sàn hoạt động ra sao, app nói chuyện với nó bằng giao thức gì,
> component nào chịu trách nhiệm gì, một lệnh đi qua những đâu, và bắt đầu dev từ lệnh nào.
>
> **Nguồn:** viết từ **code thật** đang có trong repo (đã đọc lại từng file khi soạn, không viết
> theo trí nhớ hay theo task file — chỗ nào task file khác code, tài liệu này lấy **code**).
>
> **Ngày:** 2026-09-02 · **Trạng thái epic:** 10/12 task con xong (còn `EPIC-021I`, `EPIC-021K`).

---

## 0. Đọc theo thứ tự nào

| Bạn muốn biết | Đọc phần |
| :--- | :--- |
| Testnet là cái gì, khác mainnet chỗ nào | **I** |
| App gửi HTTP/WebSocket kiểu gì tới sàn | **II** |
| File nào giữ trách nhiệm nào | **III** |
| Một lệnh đi từ nến đến khớp như thế nào | **IV** |
| Vì sao thiết kế nhiều rào chắn thế | **V** |
| Tôi muốn chạy thử ngay bây giờ | **VI** |
| Còn thiếu gì để xong epic | **VII** |

Tài liệu gốc bắt buộc đọc kèm: [`DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md`](DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md)
(ADR — **vì sao** chọn như vậy) và [`README.md`](README.md) (bảng 12 task con + trạng thái).

---

# PHẦN I — NỀN TẢNG: Binance Futures Testnet là gì

## 1.1 Testnet là bản sao của sàn thật, chạy bằng tiền giả

Binance vận hành **hai hệ thống tách biệt hoàn toàn**:

| | Mainnet | Futures Testnet |
| :--- | :--- | :--- |
| Host REST | `https://fapi.binance.com/fapi` | `https://testnet.binancefuture.com/fapi` |
| Host WebSocket | `wss://fstream.binance.com/` | `wss://fstream.binancefuture.com/` |
| Tài khoản | tài khoản Binance thật của bạn | tài khoản **riêng**, đăng ký ở `testnet.binancefuture.com` |
| API key | key thật | key **riêng, không dùng chéo được** |
| Tiền | thật | USDT giả, sàn tự cấp |
| Giá | thị trường thật | sổ lệnh riêng của testnet — **trôi lệch giá thật** |
| Độ bền dữ liệu | vĩnh viễn | **bị reset định kỳ** (mất key, mất vị thế, mất lịch sử) |

Ba hệ quả thực tế cho dev:

1. **Key mainnet dùng cho testnet sẽ trả `-2015`** (`KEY_EXPIRED` trong app này) — không phải
   "key hết hạn" theo nghĩa đen, mà là "key này không hợp lệ ở hệ thống này". Đây là lỗi phổ biến
   số một khi mới bắt đầu.
2. **Testnet reset ⇒ 401/`-2015` đột ngột** dù hôm qua vẫn chạy. Không phải bug của app.
   `EPIC-021D` phân biệt tường minh 6 nhóm lỗi (§2.2 bên dưới) đúng vì lý do này.
3. **Giá testnet ≠ giá mainnet.** App này lấy **dữ liệu chart từ mainnet** (công khai, không cần
   key, dữ liệu sạch) nhưng **đặt lệnh trên testnet** — nên giá bạn nhìn thấy không phải giá bạn
   khớp. Đó là một quyết định có chủ đích (ADR §2), và `EPIC-021K` sẽ dựng banner cảnh báo
   thường trực về nó.

## 1.2 Vì sao **USD-M Futures**, không phải Spot

Quyết định của ADR §1, có lý do kỹ thuật cứng chứ không phải sở thích:

- Mô hình khớp lệnh mô phỏng của repo (`PaperExchange`) **đã là mô hình futures từ lâu**:
  có `PositionSide.SHORT`, `long_leverage`/`short_leverage`, `MarginRiskPolicy` tính margin.
- `SignalAction` đã có `SHORT`/`COVER`, và `EmaTrendPullbackStrategy` **đang thật sự phát tín
  hiệu SHORT**.
- Spot **không short được** ⇒ một nửa hành vi backtest đã kiểm chứng sẽ không có đường ra sàn.
  Backtest và live sẽ nói hai ngôn ngữ khác nhau — đúng loại lệch mà `StrategyEngine` được thiết
  kế để không bao giờ xảy ra.

**Cái giá đã chấp nhận:** futures kéo theo position mode, margin type, leverage, funding rate,
và khả năng bị **thanh lý**. Epic xử lý 3 cái đầu tường minh; funding rate và mô hình thanh lý
được ghi nhận **chưa làm** (ADR §6) — xem Phần VII.

**COIN-M và Options nằm ngoài phạm vi** — `python-binance` có endpoint cho chúng, nhưng "thư viện
có hàm" không phải lý do để hỗ trợ.

## 1.3 Từ vựng bắt buộc (5 khái niệm, thiếu cái nào cũng đọc code không hiểu)

| Khái niệm | Nghĩa | Vì sao app quan tâm |
| :--- | :--- | :--- |
| **Position mode** | `One-way` (một symbol = một vị thế, LONG hoặc SHORT) vs `Hedge` (giữ đồng thời cả hai chiều) | Toàn bộ epic **giả định One-way**. Phát hiện Hedge ⇒ **từ chối chạy tiếp**, không chạy nửa vời (`HEDGE_MODE_UNSUPPORTED`) |
| **Margin type** | `Cross` (dùng chung số dư toàn tài khoản) vs `Isolated` (khoá margin riêng từng vị thế) | Chỉ **đọc và hiển thị**; app chưa tự đổi |
| **Leverage** | đòn bẩy theo từng symbol (vd 10x) | Đường live hiện hardcode `1.0` — nút chỉnh thuộc `EPIC-021I` |
| **Liquidation price** | giá mà tại đó sàn tự đóng vị thế do hết margin | Đọc từ sàn và hiển thị (`LivePosition.liquidation_price`); **app không tự mô hình hoá** |
| **Filters** | ràng buộc mỗi symbol: `stepSize` (bội số khối lượng), `tickSize` (bội số giá), `minNotional` (giá trị tối thiểu 1 lệnh) | Sai bất kỳ cái nào ⇒ sàn trả `-1013`. App làm tròn **trước khi gửi** (`EPIC-021C`) |

Ví dụ filters thật của `BTCUSDT` trên testnet: `stepSize=0.001`, `tickSize=0.10`,
`minNotional=100`. Nghĩa là: khối lượng phải là bội của `0.001`; giá phải là bội của `0.10`; và
`khối lượng × giá ≥ 100 USDT`. Gửi `0.0137 BTC` sẽ bị từ chối — phải làm tròn **xuống** `0.013`.

## 1.4 Bản đồ tổng thể: hai venue, ba giao thức

```plantuml
@startuml KT01_venue_map
title Sagittarius Elite Warrior — hai venue độc lập, ba giao thức

skinparam componentStyle rectangle
skinparam defaultTextAlignment center

package "Sagittarius Elite Warrior" as APP {
  [PythonBinanceClient\n(dữ liệu thị trường)] as PBC
  [BinanceWebsocketService\n(kline realtime)] as WSS
  [FuturesTradingClient\n(đặt / huỷ lệnh)] as FTC
  [FuturesAccountReader\n(kiểm tra kết nối)] as FAR
  [FuturesUserDataStream\n(sự thật về lệnh)] as FUDS
}

cloud "MAINNET — công khai, ẩn danh\napi.binance.com/api\nfapi.binance.com/fapi" as MAIN
cloud "FUTURES TESTNET — có ký (HMAC)\ntestnet.binancefuture.com/fapi" as TREST
cloud "FUTURES TESTNET — WebSocket\nfstream.binancefuture.com" as TWS

PBC --> MAIN : REST GET\nklines, exchangeInfo\n**không cần key**
WSS --> MAIN : WebSocket\nkline stream\n**không cần key**

FAR --> TREST : REST GET **có ký**\nping/time/account/positionSide
FTC --> TREST : REST POST/DELETE **có ký**\norder, order/test, openOrders
FUDS --> TWS : WebSocket **có listenKey**\nORDER_TRADE_UPDATE\nACCOUNT_UPDATE

note bottom of MAIN
  Giá **hiển thị** đến từ đây.
  Dữ liệu sạch, không cần tài khoản.
end note

note bottom of TREST
  Lệnh **thật sự khớp** ở đây.
  Giá ở đây ≠ giá bên trái.
end note

note as N1
  **Hai lựa chọn ĐỘC LẬP trong config:**
  exchange.market_data_venue = mainnet_public
  exchange.trading_venue     = disabled | futures_testnet

  Không có một cờ "testnet" chung. Cố ý (ADR §2).
end note

@enduml
```

---

# PHẦN II — GIAO THỨC: app nói chuyện với sàn thế nào

App **không tự viết HTTP client**. Nó dùng thư viện `python-binance`, và chỉ một file duy nhất
được phép khởi tạo `binance.client.Client` — `ExchangeSessionFactory`, khoá bằng một test AST
quét toàn `src/`+`scripts/`. Nhưng bạn vẫn phải hiểu giao thức bên dưới để đọc log và debug.

## 2.1 REST: hai loại request

| Loại | Cần key? | Ví dụ | Ai gọi trong app |
| :--- | :---: | :--- | :--- |
| **Public** | Không | `GET /fapi/v1/klines`, `GET /fapi/v1/exchangeInfo`, `GET /fapi/v1/ping` | `PythonBinanceClient`, `FuturesMetadataProvider` |
| **Signed** | **Có** | `POST /fapi/v1/order`, `GET /fapi/v2/account`, `GET /fapi/v3/positionRisk` | `FuturesTradingClient`, `FuturesAccountReader` |

Request **signed** phải mang thêm 3 thứ, và `python-binance` tự làm cả 3:

1. Header `X-MBX-APIKEY: <api_key>`
2. Tham số `timestamp` (millis) và `recvWindow` (mặc định 5000ms) — sàn từ chối nếu
   `timestamp` lệch quá `recvWindow` so với giờ server ⇒ lỗi `-1021` (`CLOCK_SKEW`).
3. Tham số `signature` = **HMAC-SHA256** của toàn bộ query string / form body, ký bằng
   `api_secret`. Sai ⇒ `-1022` (`BAD_SIGNATURE`).

> **Chi tiết dễ vấp:** `python-binance` gửi tham số của `GET` qua **query string**, nhưng của
> `POST`/`PUT`/`DELETE` qua **form body** (`application/x-www-form-urlencoded`) — không phải
> JSON. Fake server của repo (`tests/sanity/fake_exchange/server.py`) parse đúng theo hai cách
> đó, vì thế nó mới chạy được với client thật không sửa dòng nào.

```plantuml
@startuml KT02_signed_request
title Một REST request CÓ KÝ — ví dụ đặt lệnh thật

autonumber
participant "FuturesTradingClient" as FTC
participant "ExchangeSessionFactory" as ESF
participant "python-binance\nClient" as PB
participant "Futures Testnet\ntestnet.binancefuture.com" as EX

FTC -> FTC : _resolve_client()
FTC -> ESF : create_trading_client(credentials)
note right: chỉ file này được gọi Client(...)\n(khoá bằng test AST)
ESF -> PB : Client(api_key, api_secret, testnet=True)
PB -> EX : GET /fapi/v1/ping
note right of PB
  Client() **tự ping khi khởi tạo**.
  Đây chính là nguyên nhân BUG-045:
  resolve DI container là đã chạm mạng.
end note
EX --> PB : 200 {}

FTC -> FTC : map_order_to_futures_params(order, metadata)
note left
  Kiểm tra **tại chỗ**, trước khi ra mạng:
  quantity chia hết stepSize?
  price chia hết tickSize?
  Không ⇒ InvalidOrderForSubmissionError
  (không bao giờ tự làm tròn ngầm)
end note

FTC -> PB : futures_create_order(**params)
PB -> PB : timestamp = now_ms()\nsignature = HMAC_SHA256(body, api_secret)
PB -> EX : POST /fapi/v1/order\nHeader: X-MBX-APIKEY\nBody: symbol=BTCUSDT&side=BUY&type=MARKET\n&quantity=0.002&newClientOrderId=SEW-a91f4c72e0b8\n&positionSide=BOTH&timestamp=...&signature=...

alt Sàn chấp nhận
  EX --> PB : 200 {orderId, status:"NEW", ...}
  PB --> FTC : dict
  FTC --> FTC : trả về `order` **nguyên vẹn**
  note right
    Cố ý KHÔNG parse response thành trạng thái mới.
    Sự thật về vòng đời lệnh đến từ User Data Stream
    (ADR §4), không từ response này.
  end note
else Sàn từ chối
  EX --> PB : 400 {"code": -2019, "msg": "Margin is insufficient."}
  PB -> PB : raise BinanceAPIException
  PB --> FTC : BinanceAPIException
  FTC -> FTC : translate_binance_error(exc)
  note right
    Mã số của sàn -> lý do CÓ TÊN:
    -2019 -> INSUFFICIENT_MARGIN
    -4164 -> MIN_NOTIONAL (mã riêng của futures)
    -2022 -> REDUCE_ONLY_REJECTED
    -1003 -> RATE_LIMIT
    -1013 -> LOT_SIZE | PRICE_FILTER | MIN_NOTIONAL
             (phải đọc thêm **message text** để phân biệt —
              Binance dùng chung một mã cho cả ba)
    -1021 -> **cố ý** rơi về UNKNOWN: là lệch đồng hồ,
             không phải lỗi nội dung lệnh
  end note
  FTC --> FTC : raise OrderRejectedByExchangeError(reason)
end

@enduml
```

## 2.2 WebSocket 1 — kline công khai (đã có từ trước epic này)

`BinanceWebsocketService` mở stream nến realtime từ **mainnet**, không cần key. Hỏng cái này
chỉ làm **chart đứng**. Đây là lý do nó là một file riêng, không gộp với stream dưới đây.

## 2.3 WebSocket 2 — **User Data Stream** (trái tim của `EPIC-021H`)

Đây là kênh sàn **chủ động kể lại** chuyện gì xảy ra với tiền của bạn. Hai loại message:

| Message | Khi nào | App làm gì |
| :--- | :--- | :--- |
| `ORDER_TRADE_UPDATE` | mỗi lần trạng thái lệnh đổi: `NEW` → `PARTIALLY_FILLED` → `FILLED`, hoặc `CANCELED`/`EXPIRED` | Parse thành `Order`; nếu là **khớp thật** (`x == "TRADE"`) thì phát `OrderFilledEvent` |
| `ACCOUNT_UPDATE` | mỗi lần số dư / vị thế đổi | Đọc lại vị thế **thật** qua REST rồi phát `PositionChangedEvent` + đối chiếu state |

**Vì sao cần nó, response của lệnh chưa đủ?** Vì response `POST /fapi/v1/order` chỉ nói *"sàn đã
nhận"*. Một lệnh MARKET có thể khớp **nhiều mức giá**, khớp **một phần**, bị huỷ sau đó vì thiếu
margin, hoặc vị thế bị đổi bởi **tác nhân khác** (bạn bấm tay trên web, một phiên app khác).
`PARTIALLY_FILLED` là thứ **backtest chưa bao giờ có** — trong mô phỏng mọi lệnh khớp trọn vẹn
tức thì.

**listenKey** là vé vào cửa của stream này:

```plantuml
@startuml KT03_listenkey
title Vòng đời listenKey — uỷ quyền cho python-binance, KHÔNG tự viết

autonumber
participant "FuturesUserDataStream\n(app)" as APP
participant "BinanceSocketManager\n.futures_user_socket()" as BSM
participant "KeepAliveWebsocket\n(python-binance)" as KAW
participant "Futures Testnet" as EX

APP -> APP : credentials_provider.resolve()
alt không có key
  APP -> APP : log ERROR, return
  note right: KHÔNG raise — .start() chỉ hỏng khi\ntask nền chạy, không hỏng lúc dựng DI
end alt

APP -> BSM : futures_user_socket()
BSM -> KAW : tạo socket có keepalive
KAW -> EX : POST /fapi/v1/listenKey
EX --> KAW : {"listenKey": "abc123..."}
KAW -> EX : WS connect wss://fstream.binancefuture.com/ws/abc123...

loop mỗi khi có message
  EX --> KAW : ORDER_TRADE_UPDATE / ACCOUNT_UPDATE
  KAW --> APP : payload dict
  APP -> APP : _handle_message(payload)
end

loop định kỳ (KeepAliveWebsocket tự làm)
  KAW -> EX : POST /fapi/v1/listenKey
  note right
    Endpoint này là **create-or-extend**:
    - key còn hạn -> trả LẠI CHÍNH key đó
    - key đã hết  -> trả key MỚI
    Thư viện tự reconnect bằng key mới khi nó đổi.
  end note
  EX --> KAW : {"listenKey": ...}
end

note over APP, KAW
  **Quyết định triển khai (`EPIC-021H` §6.1):** app KHÔNG tự viết bộ định thời
  keepalive. Đã đọc thẳng source `binance/ws/keepalive_websocket.py` để xác nhận
  thư viện làm đúng yêu cầu "gia hạn định kỳ, tái tạo khi mất kết nối".
  Tự viết lại = một bản triển khai thứ hai không ai review.
end note

@enduml
```

> **Rủi ro nếu làm sai (và vì sao phải hiểu):** reconnect bằng listenKey đã hết hạn sẽ **nối
> được nhưng không nhận được gì** — dạng hỏng im lặng tệ nhất. App tưởng mình đang theo dõi
> lệnh, thực ra đang mù.

## 2.4 Toàn bộ endpoint app này thật sự gọi

Đây là danh sách **đã verify bằng cách đọc source `python-binance`**, không phải chép từ docs
Binance (docs không phải lúc nào cũng khớp version thư viện đang cài):

| Method | Path | Hàm `python-binance` | Ai gọi |
| :--- | :--- | :--- | :--- |
| GET | `/fapi/v1/ping` | ctor `Client()` | mọi client (tự ping khi dựng) |
| GET | `/fapi/v1/time` | `futures_time()` | `FuturesAccountReader` (lệch đồng hồ) |
| GET | `/fapi/v1/exchangeInfo` | `futures_exchange_info()` | `FuturesMetadataProvider` (filters) |
| GET | `/fapi/v1/klines` | kline generator | dữ liệu nến |
| GET | `/fapi/v2/account` | `futures_account()` — **v2** | số dư USDT |
| GET | `/fapi/v1/positionSide/dual` | `futures_get_position_mode()` | phát hiện Hedge mode |
| GET | `/fapi/v3/positionRisk` | `futures_position_information()` — **v3** | `get_positions()` |
| GET | `/fapi/v1/openOrders` | `futures_get_open_orders()` | `get_open_orders()` |
| POST | `/fapi/v1/order/test` | `futures_create_test_order()` | **dry-run** (`VALIDATE_ONLY`) |
| POST | `/fapi/v1/order` | `futures_create_order()` | **lệnh thật** (`LIVE`) |
| DELETE | `/fapi/v1/order` | `futures_cancel_order()` | huỷ 1 lệnh |
| DELETE | `/fapi/v1/allOpenOrders` | `futures_cancel_all_open_orders()` | huỷ tất cả |
| POST/PUT | `/fapi/v1/listenKey` | `futures_stream_get_listen_key()` / `_keepalive()` | User Data Stream |

> ⚠️ Chú ý hai số version dễ sai: `account` là **v2**, `positionRisk` là **v3**. Bản nháp thiết
> kế của task ghi `positionRisk` là v2 — **sai**; code lấy theo `client.py` thật.

---

# PHẦN III — KIẾN TRÚC: component nào làm gì

## 3.1 Bản đồ component (AS-BUILT, không phải bản vẽ kế hoạch)

```plantuml
@startuml KT04_as_built_component
title EPIC-021 — kiến trúc NHƯ ĐÃ DỰNG (2026-09-02): chiều phụ thuộc

skinparam componentStyle rectangle
skinparam linetype ortho
skinparam nodesep 12
skinparam ranksep 28

package "1. PRESENTATION" #F5F5F5 {
  [main.py CLI\n4 mốc: exchange-status / order-preview\norder-dry-run / trade-once] as CLI
  [OrderFeed  (Feed thứ 4)] as FEED
  [Màn Giao dịch — **EPIC-021I CHƯA LÀM**] as SCREEN #FFCDD2
}

package "2. APPLICATION" #EEF5FF {
  [MarketTickEventHandler] as MTH
  [LiveTradingCoordinator] as LTC
  [EnableTradingCommandHandler] as ETH
  [ExecuteOrderCommandHandler\n**nơi DUY NHẤT dựng LIVE**] as EOH
  [PreviewOrderQueryHandler] as POH
  [TradingSessionState  (RAM)] as TSS
  [position_state_reconciler] as PSR
}

package "  PORTS (application/ports)" #E1F5FE {
  interface ITradingClient as ITC
  interface ITradingAccountReader as ITAR
  interface IUserDataStream as IUDS
}

package "3. DOMAIN — không import SDK nào" #E8F5E9 {
  [Order / OrderStatus / ClientOrderId\nLivePosition] as OM
  [TradingLimitPolicy\n4 hạn mức] as TLP
  [OrderQuantityRoundingPolicy\nstep / tick / minNotional] as OQR
  [TradingVenue\nDISABLED | FUTURES_TESTNET] as TV
  [4 event\nOrderSubmitted / OrderFilled\nOrderRejected / PositionChanged] as EVT
}

package "4. INFRASTRUCTURE" #FFF8E1 {
  [ExchangeSessionFactory\n**nơi DUY NHẤT dựng Client()**] as ESF
  [FuturesTradingClient] as FTC
  [FuturesAccountReader] as FAR
  [FuturesUserDataStream] as FUDS
  [EnvFirstCredentialsProvider] as ECP
}

cloud "Futures Testnet" as EX
folder "env / secrets.local.json\nNGOÀI git" as SEC

' --- luồng chính: từ nến tới lệnh ---
MTH -down-> LTC : **gọi trực tiếp**\nhandle(signal)
LTC -down-> EOH : ExecuteOrderCommand
EOH -down-> POH
EOH -right-> TSS
CLI -down-> EOH
ETH -right-> TSS

' --- application dùng domain ---
EOH -down-> TLP
POH -down-> OQR
EOH -down-> TV

' --- application chỉ biết PORT, không biết adapter ---
EOH ..> ITC
ETH ..> ITAR
ETH ..> IUDS

' --- infrastructure implement port (mũi tên NGƯỢC lên) ---
ITC <|.. FTC
ITAR <|.. FAR
IUDS <|.. FUDS

' --- infrastructure ra ngoài ---
ESF -down-> FTC
ESF -down-> FAR
ECP -down-> SEC
FTC -down-> EX
FAR -down-> EX
FUDS -down-> EX
FUDS -up-> PSR
FUDS ..> EVT
EVT ..> FEED
FEED ..> SCREEN

note as N1 #FFCDD2
  **Diagram này khác bản vẽ kế hoạch — cố ý.**
  `design/03_to_be_component.puml` vẽ
  StrategyEngine --> LiveTradingCoordinator qua **event bus**.
  Triển khai `EPIC-021G` phát hiện đó là lỗ hổng an toàn thật (§5.4)
  và đổi sang **lời gọi trực tiếp**.
  Bản vẽ kế hoạch giữ làm lịch sử; **code mới là sự thật**.
end note

note as N2 #E8F5E9
  **Luật chiều phụ thuộc:**
  Presentation -> Application -> Domain
  Infrastructure -> (implement) Ports của Application
  **Domain không phụ thuộc ai.** Không import
  `binance`, không import Qt.
end note

@enduml
```

## 3.2 Bốn Port, và vì sao `ITradingClient` tách khỏi `IExchangeClient`

| Port | Trách nhiệm | Ai implement |
| :--- | :--- | :--- |
| `IExchangeClient` | **chỉ đọc** dữ liệu thị trường (kline, danh sách symbol) | `PythonBinanceClient` |
| `ITradingAccountReader` | **chỉ đọc** trạng thái tài khoản (số dư, position mode, lệch giờ) — **không bao giờ raise**, luôn trả `ExchangeConnectionStatus` có tên lỗi | `FuturesAccountReader` |
| `ITradingClient` | **ghi**: đặt / huỷ lệnh, đọc vị thế & lệnh mở | `FuturesTradingClient` |
| `IUserDataStream` | mở/đóng kênh sự thật từ sàn | `FuturesUserDataStream` |

> **Vì sao không nhét `place_order` vào `IExchangeClient` cho gọn?** Vì hai thứ có **hậu quả
> khi hỏng** hoàn toàn khác nhau: hỏng đọc kline = chart đứng; hỏng đặt lệnh = mất tiền. Trộn
> chúng nghĩa là mọi consumer chỉ cần đọc chart cũng **cầm trong tay** khả năng đặt lệnh. Đây là
> áp dụng trực tiếp `architecture-rule.md` §5.5: *"đổi cái này có bắt buộc phải sửa cái kia
> không?"* — không.

Một chi tiết DI quan trọng, đã suýt gây crash 3 lần trong epic:

> `ITradingClient` chỉ được **đăng ký có điều kiện** (khi `TradingVenue != DISABLED`).
> Vì thế `EnableTradingCommandHandler`, `ExecuteOrderCommandHandler` và `FuturesUserDataStream`
> **không** phụ thuộc nó trực tiếp — chúng nhận `session_factory` + `credentials_provider` +
> `metadata_provider` (luôn có) và **tự dựng** `FuturesTradingClient` bên trong. Nếu không,
> chúng sẽ không **dựng được** khi trading tắt — mà chính chúng là nơi phải báo cáo
> "trading đang tắt". Ngược lại `IUserDataStream` đăng ký **vô điều kiện** (chỉ đọc, cùng nhóm
> rủi ro với `ITradingAccountReader`).

---

# PHẦN IV — ĐƯỜNG ĐI CỦA MỘT LỆNH

## 4.1 Từ một cây nến đến một lệnh khớp thật

```plantuml
@startuml KT05_order_path
title Đường đi đầy đủ của một lệnh live

autonumber
participant "MarketTickEventHandler" as MTH
participant "StrategyEngine" as SE
participant "LiveTradingCoordinator" as LTC
participant "ExecuteOrderCommandHandler" as EOH
participant "TradingSessionState" as TSS
participant "TradingLimitPolicy" as TLP
participant "PreviewOrderQueryHandler" as POH
participant "FuturesTradingClient" as FTC
participant "Futures Testnet" as EX
participant "FuturesUserDataStream" as FUDS
participant "OrderFeed -> UI" as UI

MTH -> SE : on_tick(candle)
SE --> MTH : Signal | None
note right of MTH
  **KHÔNG qua event bus.**
  Gọi thẳng — xem §5.4.
end note

MTH -> LTC : handle(signal)
LTC -> LTC : signal.symbol == live_symbol?
LTC -> LTC : tính quantity\n(% equity, làm tròn theo stepSize)
LTC -> EOH : dispatch(ExecuteOrderCommand(live=True))

group **3 CỔNG AN TOÀN** (chặn là dừng ngay)
  EOH -> EOH : 1. TradingVenue == FUTURES_TESTNET?
  EOH -> TSS : 2. session_state.enabled?
  EOH -> EOH : 3. check_connection() reachable + One-way?
end

EOH -> POH : preview(order_request)
POH --> EOH : Order đã chuẩn hoá\n+ client_order_id "SEW-..."\n+ estimated_notional

group **4 HẠN MỨC** (luôn đánh giá cả 4, chặn theo cái đầu tiên hỏng)
  EOH -> TLP : evaluate(context)
  TLP --> EOH : (orders/session, notional, positions/symbol, interval)
end

alt live == False (dry-run)
  EOH --> LTC : kết quả preview, **không gửi gì**
else live == True
  EOH -> FTC : place_order(order)   [OrderSubmissionMode.**LIVE**]
  note right of EOH
    **Nơi DUY NHẤT** trong toàn app
    được phép dựng LIVE (khoá bằng test AST)
  end note
  FTC -> EX : POST /fapi/v1/order (có ký)
  EX --> FTC : 200 {orderId, status:"NEW"}
  FTC --> EOH : order (nguyên vẹn)
  EOH -> TSS : record_order_sent(symbol, now)
  note right of TSS
    Ghi nhận **lạc quan**: đánh dấu symbol
    là "đang mở" NGAY khi gửi, trước khi
    biết có khớp không. Thà chặn nhầm lệnh
    thứ hai còn hơn để lọt.
  end note
end

... vài trăm ms sau, sàn chủ động kể lại ...

EX -> FUDS : ORDER_TRADE_UPDATE (x=TRADE, X=PARTIALLY_FILLED)
FUDS -> UI : **OrderFilledEvent**(order, fill_price, fill_qty)
EX -> FUDS : ACCOUNT_UPDATE
FUDS -> EX : GET /fapi/v3/positionRisk (đọc lại sự thật)
EX --> FUDS : [position]
FUDS -> TSS : reconcile_position_state()
note right of TSS
  Sàn thắng. Lệch với niềm tin nội bộ
  -> log WARNING, không im lặng ghi đè.
end note
FUDS -> UI : **PositionChangedEvent**(position)

@enduml
```

## 4.2 Phễu an toàn: 3 cổng + 4 hạn mức

```plantuml
@startuml KT06_safety_funnel
title Phễu an toàn — một lệnh phải qua 7 chốt

start
:ExecuteOrderCommand(live=True);

if (TradingVenue == FUTURES_TESTNET?) then (không)
  #FFCDD2:BLOCKED\nTRADING_VENUE_DISABLED;
  stop
endif

if (TradingSessionState.enabled?) then (không)
  #FFCDD2:BLOCKED\nTRADING_SWITCH_OFF;
  stop
endif

if (Kết nối OK + One-way mode?) then (không)
  #FFCDD2:BLOCKED\nCONNECTION_NOT_READY;
  stop
endif

:PreviewOrderQueryHandler\nlàm tròn theo stepSize/tickSize\ntính estimated_notional;

if (Đã gửi < 20 lệnh trong phiên?) then (không)
  #FFE0B2:BLOCKED\nMAX_ORDERS_PER_SESSION;
  stop
endif

if (notional <= 500 USDT?) then (không)
  #FFE0B2:BLOCKED\nMAX_NOTIONAL_PER_ORDER;
  stop
endif

if (Symbol này đang có < 1 vị thế?) then (không)
  #FFE0B2:BLOCKED\nMAX_POSITIONS_PER_SYMBOL;
  stop
endif

if (Đã >= 60s từ lệnh trước cùng symbol?) then (không)
  #FFE0B2:BLOCKED\nMIN_ORDER_INTERVAL;
  stop
endif

#C8E6C9:POST /fapi/v1/order\n**LỆNH THẬT**;
:record_order_sent();
stop

note right
  **3 cổng đỏ** = trạng thái hệ thống (bật/tắt/kết nối).
  **4 hạn mức cam** = chống vòng lặp tín hiệu lỗi
  bắn hàng trăm lệnh. Giá trị lấy từ config:
    trading.max_orders_per_session      = 20
    trading.max_notional_per_order_usdt = 500
    trading.max_positions_per_symbol    = 1
    trading.min_order_interval_seconds  = 60
  **Không có công tắc tắt riêng từng hạn mức** —
  chỉ chỉnh được ngưỡng số.
end note

@enduml
```

**Chi tiết Boundary Value Analysis đã cân nhắc kỹ** (đọc `trading_limit_policy.py`):

| Hạn mức | Toán tử | Nghĩa tại biên |
| :--- | :---: | :--- |
| `max_orders_per_session` | `<` | Đã gửi đúng 20 ⇒ **chặn** lệnh 21 |
| `max_notional_per_order` | `<=` | notional đúng bằng 500 ⇒ **cho qua** |
| `max_positions_per_symbol` | `<` | đang có đúng 1 vị thế ⇒ **chặn** lệnh mới |
| `min_order_interval` | `>=` | đúng 60s từ lệnh trước ⇒ **cho qua**; chưa từng gửi ⇒ luôn qua |

## 4.3 Vòng đời một `Order`

```plantuml
@startuml KT07_order_lifecycle
title OrderStatus — vòng đời, với ma trận chuyển hợp lệ

[*] --> NEW : app dựng Order\n(client_order_id = "SEW-" + 12 hex)

NEW --> PARTIALLY_FILLED : ORDER_TRADE_UPDATE\nx=TRADE, khớp một phần
NEW --> FILLED : khớp trọn ngay (MARKET thường thế)
NEW --> CANCELED : DELETE /fapi/v1/order
NEW --> REJECTED : sàn từ chối (filters, margin)
NEW --> EXPIRED : hết hạn theo timeInForce

PARTIALLY_FILLED --> FILLED : khớp nốt
PARTIALLY_FILLED --> CANCELED : huỷ phần còn lại
PARTIALLY_FILLED --> EXPIRED : hết hạn phần còn lại

FILLED --> [*]
CANCELED --> [*]
REJECTED --> [*]
EXPIRED --> [*]

note right of PARTIALLY_FILLED
  Trạng thái **backtest chưa bao giờ có**.
  Trong PaperExchange mọi lệnh khớp trọn vẹn
  tức thì. Đây là lý do User Data Stream
  tồn tại (ADR §4).
end note

note left of NEW
  `Order` là **frozen dataclass**.
  Đổi trạng thái = tạo Order MỚI qua
  dataclasses.replace, không sửa tại chỗ —
  không ai quan sát được trạng thái nửa vời.

  `NEW` cũng là mặc định **trước khi gửi**:
  order là NEW ngay khi app dựng nó, sàn chỉ
  xác nhận hoặc đẩy tiếp, không bao giờ tự gán.
end note

@enduml
```

Ma trận này được **thực thi bằng hàm** `is_valid_transition(current, target)`, không phải quy
ước ai cũng phải nhớ. Hai chi tiết dễ bỏ sót:

- **4 trạng thái kết thúc không có đích hợp lệ nào — kể cả chính nó.** Quan sát lại một trạng
  thái kết thúc không đổi là chuyện idempotency của caller, không phải một "transition".
- **Không có `PARTIALLY_FILLED → PARTIALLY_FILLED`.** Khớp thêm một phần nữa không đi qua hàm
  này; nó là một `OrderFilledEvent` mới mang `fill_price`/`fill_quantity` của **lần khớp đó**
  (đọc từ `"L"`/`"l"` trong payload, **không** phải tổng luỹ kế `"ap"`/`"z"`).

## 4.4 `VALIDATE_ONLY` vs `LIVE` — một tham số constructor, không phải cờ mỗi lần gọi

```
OrderSubmissionMode.VALIDATE_ONLY  ->  POST /fapi/v1/order/test   (sàn kiểm, KHÔNG tạo lệnh)
OrderSubmissionMode.LIVE           ->  POST /fapi/v1/order        (lệnh THẬT)
```

Đây là **tham số constructor** của `FuturesTradingClient`, cố ý không phải tham số mỗi lần gọi:
một instance chỉ phục vụ đúng một chế độ suốt đời nó. Không thể "lỡ tay truyền nhầm cờ" ở một
call site nào đó.

`/fapi/v1/order/test` xác thực **đầy đủ**: chữ ký, quyền của key, và toàn bộ payload (filters,
minNotional) — nhưng không bao giờ đưa vào matching engine. Đó là lý do `order-dry-run` là mốc
kiểm tra **cực kỳ giá trị**: nó chứng minh mọi thứ đúng, trừ việc mất tiền.

---

# PHẦN V — AN TOÀN: vì sao thiết kế như vậy

## 5.1 `TradingVenue` **không có** member `MAINNET`

```python
class TradingVenue(str, Enum):
    DISABLED = "disabled"
    FUTURES_TESTNET = "futures_testnet"
```

Không phải "mainnet bị tắt bằng config" — mà là **không tồn tại như một lựa chọn trong kiểu dữ
liệu**. Muốn giao dịch mainnet phải sửa code + review, không phải sửa một dòng JSON. Rào an toàn
bằng **type**, không bằng cấu hình (ADR §3).

Config sai/thiếu ⇒ mặc định `DISABLED`, **có log WARNING**, không bao giờ mặc định về testnet.

## 5.2 Công tắc giao dịch **luôn bắt đầu TẮT**, mỗi phiên

`TradingSessionState` là singleton trong RAM, **cố ý không đọc** giá trị đã lưu của
`trading.enabled` lúc boot. Đây là **ngoại lệ có chủ đích duy nhất** với quy ước "nhớ thứ user
đặt lần trước" của `EPIC-010`:

> Mở app lên không bao giờ được ở trạng thái sẵn sàng bắn lệnh.

## 5.3 Reconciliation: bật giao dịch là một **hành động có hệ quả**

`EnableTradingCommand` không phải cái checkbox. Khi bật:

1. Đọc **toàn tài khoản** (`get_positions()` / `get_open_orders()` **không truyền symbol**).
2. Nếu sàn đang có **bất kỳ vị thế nào** ⇒ **từ chối bật**, trả về danh sách vị thế đó.
   App **không bao giờ** tự nhận (auto-adopt) hay tự đóng vị thế nó không mở.
3. Chỉ khi tài khoản sạch mới `enable()` và `IUserDataStream.start()`.

## 5.4 Bẫy thật đã tránh: **backtest suýt bắn được lệnh thật**

Đây là phát hiện an toàn nghiêm trọng nhất của cả epic, đáng để mọi dev trong team biết.

```plantuml
@startuml KT08_backtest_hazard
title Lỗ hổng đã phát hiện và sửa trong EPIC-021G

skinparam componentStyle rectangle

package "THIẾT KẾ BAN ĐẦU (nguy hiểm)" #FFEBEE {
  [StrategyEngine\n(live)] as SE1
  [StrategyEngine\n(BACKTEST)] as SE2
  queue "IEventPublisher\n**BUS TOÀN CỤC DÙNG CHUNG**" as BUS
  [LiveTradingCoordinator\n.on(SignalGeneratedEvent)] as LTC1
  cloud "LỆNH THẬT" as EX1

  SE1 --> BUS : SignalGeneratedEvent
  SE2 --> BUS : SignalGeneratedEvent
  BUS --> LTC1
  LTC1 --> EX1
}

package "ĐÃ SỬA (as-built)" #E8F5E9 {
  [MarketTickEventHandler] as MTH
  [StrategyEngine\n(live)] as SE3
  [StrategyEngine\n(BACKTEST)] as SE4
  queue "IEventPublisher\n(vẫn dùng chung)" as BUS2
  [LiveTradingCoordinator] as LTC2
  cloud "LỆNH THẬT" as EX2

  MTH --> SE3 : on_tick(candle)
  SE3 --> MTH : **return Signal**
  MTH --> LTC2 : **handle(signal)** — gọi trực tiếp
  LTC2 --> EX2
  SE3 ..> BUS2 : (vẫn phát event, cho log/UI)
  SE4 ..> BUS2 : (backtest phát event)
  BUS2 ..> LTC2 #red : **KHÔNG CÒN ĐƯỜNG NÀY**
}

note bottom of BUS
  `RunHistoricalTickBacktestCommandHandler`
  dùng **cùng** IEventPublisher singleton.
  => Chạy một backtest sẽ bắn SignalGeneratedEvent
  vào đúng coordinator đang cầm quyền đặt lệnh thật.
  Chỉ còn 3 cổng an toàn chắn — mà một phiên
  vừa bật trading hợp lệ sẽ **qua cả 3**.
end note

@enduml
```

Cách sửa: `StrategyEngine.on_tick()` **vốn đã return** `Signal` cho caller. `MarketTickEventHandler`
gọi thẳng `LiveTradingCoordinator.handle(signal)` với giá trị đó, **không đụng bus**. Không code
path nào của backtest chạm tới class này nữa.

Ghi chú: phát hiện này **không** đến từ một test đỏ — nó đến từ việc đọc kỹ code khởi tạo của
`RunHistoricalTickBacktestCommandHandler` trước khi nối dây. Bài học: với đường đi tiền thật,
đọc chéo call graph trước khi tin vào bản vẽ.

## 5.5 Guard tự động — luật được **thực thi**, không phải quy ước truyền miệng

| Guard | Cấm gì | File |
| :--- | :--- | :--- |
| AST scan | Chỉ `ExecuteOrderCommandHandler` được viết `OrderSubmissionMode.LIVE` | `tests/unit/infrastructure/binance/test_order_submission_mode_live_is_restricted.py` |
| AST scan | Chỉ `ExchangeSessionFactory` được gọi `binance.client.Client(...)` | `test_only_the_session_factory_constructs_binance_client.py` |
| AST scan | `ui/qml/` không được import `ui/screens/` (`EPIC-021L`, đóng `BUG-082`) | `test_qml_library_does_not_import_screens.py` |

Cả 3 đều quét **node AST**, không quét text — nên docstring **giải thích** luật không tự vi phạm
luật đó. Cả 3 đều có test "mutation-verify" chứng minh guard thật sự bắt được vi phạm.

## 5.6 Secret không bao giờ vào git

Thứ tự ưu tiên (`EnvFirstCredentialsProvider`): **biến môi trường** → `secrets.local.json`
(đã `.gitignore`) → không có. `ExchangeCredentials` được thiết kế để `repr()`/`str()`/f-string/
traceback **đều không rò** secret — có test kiểm cả 4 đường.

---

# PHẦN VI — BẮT ĐẦU DEV: 30 phút đầu tiên

## 6.1 Lấy key Futures Testnet

1. Vào `https://testnet.binancefuture.com`, đăng nhập (tài khoản **riêng**, không phải tài khoản
   Binance thật).
2. Vào mục API Key ⇒ lấy `API Key` + `API Secret`.
3. Sàn tự cấp USDT giả (thường ~15.000).
4. Kiểm tra **position mode phải là One-way** (mục Preference). Hedge mode ⇒ app từ chối chạy.

## 6.2 Cấu hình

**Cách 1 — biến môi trường (khuyên dùng, không để secret lên đĩa):**

```bash
export BINANCE_FUTURES_TESTNET_API_KEY="..."
export BINANCE_FUTURES_TESTNET_API_SECRET="..."
```

**Cách 2 — file (đã gitignore):** `src/config/secrets.local.json`

Rồi bật venue giao dịch trong `src/config/user_config.json`:

```json
{ "exchange": { "trading_venue": "futures_testnet" } }
```

Kiểm tra cấu hình đang thắng ở nguồn nào (chạy được cả khi **chưa** có key):

```bash
PYTHONPATH=. .venv/bin/python Sagittarius_Elite_Warrior/scripts/epic021b_credentials_probe.py
```

## 6.3 Bốn mốc CLI — chạy **đúng thứ tự này**, mỗi mốc nguy hiểm hơn mốc trước

```plantuml
@startuml KT09_cli_ladder
title Thang leo 4 mốc CLI — rủi ro tăng dần

skinparam defaultTextAlignment center

rectangle "1. exchange-status" #E3F2FD {
  card "Chạm sàn lần đầu.\n**Chỉ ĐỌC.**\nThấy: số dư USDT thật,\nlệch đồng hồ, position mode." as A
}
rectangle "2. order-preview" #E8F5E9 {
  card "**KHÔNG chạm mạng để đặt lệnh.**\nThấy: Order đã chuẩn hoá,\nclient_order_id, hoặc lý do\ntừ chối có tên (MIN_NOTIONAL)." as B
}
rectangle "3. order-dry-run" #FFF9C4 {
  card "POST /fapi/v1/order/**test**\nSàn kiểm chữ ký + quyền + payload.\n**0 lệnh được tạo.**" as C
}
rectangle "4. trade-once --live" #FFCDD2 {
  card "POST /fapi/v1/order\n**LỆNH THẬT ĐẦU TIÊN.**\nBỏ --live thì dừng ở dry-run." as D
}

A -down-> B
B -down-> C
C -down-> D

note right of A
  python Sagittarius_Elite_Warrior/src/main.py exchange-status
end note
note right of B
  ... order-preview --symbol BTCUSDT --side BUY --qty 0.0137
end note
note right of C
  ... order-dry-run --symbol BTCUSDT --side BUY --qty 0.002
end note
note right of D
  ... trade-once --symbol BTCUSDT --interval 1m \
      --strategy <key> --live
end note

@enduml
```

> ⚠️ **`trade-once` hiện KHÔNG tự gọi `EnableTradingCommand`.** Nó đi thẳng vào
> `ExecuteOrderCommand`, mà cổng an toàn số 2 đòi `session_state.enabled == True`. Hiện chưa có
> CLI nào bật công tắc đó — nó sẽ đến cùng **màn Giao dịch (`EPIC-021I`)**. Đây là một khoảng
> trống đã biết, ghi trong `EPIC-021H` §6.6, không phải bug.

Quan sát sàn kể lại vòng đời lệnh, ở terminal thứ hai:

```bash
PYTHONPATH=. .venv/bin/python \
  Sagittarius_Elite_Warrior/scripts/epic021h_user_stream_probe.py --seconds 120
```

## 6.4 Chạy test — 4 tier, biết tier nào chứng minh cái gì

```plantuml
@startuml KT10_test_tiers
title Bốn tier test — cái nào chạm mạng thật?

skinparam componentStyle rectangle

rectangle "**Unit**\ntests/unit/" #E8F5E9 {
  card "Logic thuần, 0 mạng.\nTrading limits, mapper, parser,\nAST guards, OrderBookState.\n~3.200 test" as U
}
rectangle "**Integration**\ntests/integration/" #E3F2FD {
  card "Chạm **fake server nội bộ**\n(tests/sanity/fake_exchange/).\nClient python-binance THẬT chạy,\nchỉ base URL bị đổi." as I
}
rectangle "**Sanity**\ntests/sanity/" #FFF9C4 {
  card "Boot app thật, DI thật.\n**Im lặng là assertion**:\n0 Qt message, 0 log WARNING+.\n24 test" as S
}
rectangle "**Testnet**\ntests/testnet/" #FFCDD2 {
  card "**CHẠM SÀN THẬT, KEY THẬT.**\nopt-in, 2 lớp cổng.\n3 test" as T
}

U -[hidden]right-> I
I -[hidden]right-> S
S -[hidden]right-> T

note bottom of T
  **Hai lớp cổng, cố ý dư thừa:**
  1. ci-local.ps1 --ignore tier này ở MỌI mode (kể cả -Full)
  2. conftest.py đòi SEW_TESTNET_TESTS=1 **VÀ** có credentials

  Một lớp đã từng không đủ: tier chỉ dựa vào skip điều kiện
  sẽ chạy thật ngay khi ai đó tình cờ có biến môi trường đó.
end note

note bottom of I
  **Không hand-write double cho port.**
  Đó là hình dạng đã sinh ra BUG-026/BUG-027:
  bản triển khai viết tay lặng lẽ trôi khỏi interface.
  Thay thế chỉ ở **ranh giới mạng, tại cấu hình**.
end note

@enduml
```

Lệnh chạy (cổng đầy đủ, **không** chạm sàn thật):

```powershell
.\scripts\ci-local.ps1 -Full
```

Chạy tier testnet **có chủ đích**:

```powershell
$env:SEW_TESTNET_TESTS = "1"
.\scripts\ci-local.ps1 -TestnetOnly
```

Thiếu điều kiện ⇒ **skip với lý do phân biệt được**, không đỏ:

```text
SKIPPED [1] thiếu SEW_TESTNET_TESTS=1 — tier này không chạy trong CI thường
SKIPPED [1] có SEW_TESTNET_TESTS=1 nhưng không tìm thấy credentials Futures Testnet
```

> **Luật đọc kết quả CI (`ONBOARDING.md` §5):** `ci-local.ps1` in ra `LOG_FILE:`. Phải `grep`
> file đó cho `FAILED|ERROR|Traceback|ResourceWarning` rồi mới được nói "xanh". Ở chế độ
> offscreen, Qt xả nhiều `TypeError` **vô hại** ra stderr **sau** dòng tổng kết pytest — `| tail`
> sẽ cho bạn xem nhầm đống nhiễu đó.

---

# PHẦN VII — CÒN LẠI GÌ

## 7.1 Hai task con chưa xong

| Task | Nội dung | Chặn bởi |
| :--- | :--- | :--- |
| **`EPIC-021I`** | **Màn hình Giao dịch mới**: bảng vị thế, bảng lệnh chờ, công tắc bật giao dịch, thẻ tài khoản | Đang chờ **mockup** từ user (task file yêu cầu hỏi trước, không tự sinh lại) |
| **`EPIC-021K`** | Banner môi trường toàn cục + **Emergency Stop** + trade marker trên chart | `EPIC-021I` |

`EPIC-021I` cũng là nơi sẽ có CLI/UI để gọi `EnableTradingCommand` — mắt xích còn thiếu ở §6.3.

## 7.2 Đã ghi nhận là **chưa mô hình hoá** (cố ý, ADR §6)

- **Funding rate** — futures perpetual tính phí funding mỗi 8h. App chưa tính.
- **Mô hình thanh lý** — app **đọc và hiển thị** `liquidationPrice` từ sàn nhưng không tự tính,
  không cảnh báo khi giá tiến gần.
- **Đổi leverage / margin type từ app** — chỉ đọc.
- **Multi-symbol live** — `StrategyEngine` giữ state chỉ số có thể thay đổi (EMA...); nạp nến
  hai symbol vào một engine sẽ **làm hỏng state**. Muốn đa symbol phải một engine mỗi symbol.

---

# PHỤ LỤC A — Bản đồ file

| Tầng | File | Trách nhiệm |
| :--- | :--- | :--- |
| Domain | `domain/trading/order.py` | `Order` frozen dataclass |
| | `domain/trading/order_status.py` | `OrderStatus` + ma trận chuyển hợp lệ |
| | `domain/trading/client_order_id.py` | sinh `SEW-` + 12 hex (≤36 ký tự) |
| | `domain/trading/live_position.py` | `LivePosition`, `LiquidationPrice` |
| | `domain/trading/order_submission_mode.py` | `VALIDATE_ONLY` \| `LIVE` |
| | `domain/trading/order_rejection_reason.py` | 7 lý do từ chối có tên |
| | `domain/trading/policies/trading_limit_policy.py` | 4 hạn mức |
| | `domain/value_objects/trading_venue.py` | `DISABLED` \| `FUTURES_TESTNET` |
| | `domain/value_objects/exchange_connection_status.py` | 6 `ConnectionFailureKind` |
| | `domain/events/order_*.py`, `position_changed_event.py` | 4 event |
| Application | `application/ports/i_trading_client.py` | port ghi |
| | `application/ports/i_trading_account_reader.py` | port đọc tài khoản |
| | `application/ports/i_user_data_stream.py` | port stream |
| | `application/services/trading_session_state.py` | state RAM, luôn khởi đầu tắt |
| | `application/services/live_trading_coordinator.py` | Signal → ExecuteOrderCommand |
| | `application/services/position_state_reconciler.py` | sàn thắng, lệch thì WARNING |
| | `application/use_cases/trading/enable_trading/` | bật + reconcile |
| | `application/use_cases/trading/execute_order/` | 3 cổng + 4 hạn mức + LIVE |
| | `application/event_handlers/.../market_tick_event_handler.py` | gọi thẳng coordinator |
| Infrastructure | `infrastructure/binance/exchange_session_factory.py` | **nơi duy nhất** dựng `Client()` |
| | `infrastructure/binance/futures_trading_client.py` | đặt/huỷ/đọc lệnh & vị thế |
| | `infrastructure/binance/futures_account_reader.py` | `check_connection()` |
| | `infrastructure/binance/futures_user_data_stream.py` | User Data Stream |
| | `infrastructure/binance/futures_order_payload_mapper.py` | domain ↔ payload Binance |
| | `infrastructure/binance/binance_error_translator.py` | mã lỗi → lý do có tên |
| | `infrastructure/binance/user_data_event_parser.py` | parse message stream |
| | `infrastructure/credentials/env_first_credentials_provider.py` | env → file → none |
| Presentation | `presentation/ui/common/order_feed.py` | Feed thứ 4 |
| | `presentation/cli/{order_preview,order_dry_run,trade_once}_cmd.py` | 4 mốc CLI |
| Test | `tests/sanity/fake_exchange/` | fake server nói giao thức Binance |
| | `tests/testnet/` | tier opt-in chạm sàn thật |
| Script | `scripts/epic021{a,b,c}_*_probe.py`, `epic021h_user_stream_probe.py` | 4 probe quan sát |

---

# PHỤ LỤC B — Render các diagram

Mọi diagram trong tài liệu này là mã PlantUML trong khối ` ```plantuml `. **Cả 10 diagram đã được
render thật khi soạn tài liệu này** (PlantUML 1.2024.7 + Graphviz 2.43) — không có lỗi cú pháp.

- **VS Code**: extension *PlantUML* (jebbs) → `Alt+D`.
- **Online**: dán vào `https://www.plantuml.com/plantuml`.
- **CLI** — trích toàn bộ 10 diagram từ chính file này rồi render một lượt:

  ```bash
  # cần: java + graphviz (apt-get install -y graphviz)
  #      plantuml.jar tải từ github.com/plantuml/plantuml/releases
  mkdir -p /tmp/kt && cd /tmp/kt
  python3 - <<'PY'
  import re, pathlib
  doc = pathlib.Path("Tasks/epics/EPIC-021_ket_noi_binance_futures_testnet/"
                     "KNOWLEDGE_TRANSFER_tu_0_den_hero.md").read_text(encoding="utf-8")
  for i, b in enumerate(re.findall(r"```plantuml\n(.*?)```", doc, re.S), 1):
      n = re.search(r"@startuml\s+(\S+)", b)
      pathlib.Path(f"{n.group(1) if n else i}.puml").write_text(b, encoding="utf-8")
  PY
  java -jar plantuml.jar -tpng -nometadata *.puml
  ```

> **Graphviz là bắt buộc** cho diagram dạng component/state (KT01, KT04, KT07, KT08, KT09, KT10).
> Thiếu nó, PlantUML vẫn tạo file PNG nhưng bên trong là **thông báo lỗi**, không phải diagram —
> một cái bẫy im lặng đáng biết. Diagram dạng sequence/activity (KT02, KT03, KT05, KT06) không
> cần Graphviz.
>
> Muốn chỉ kiểm cú pháp mà không render: `java -jar plantuml.jar -checkonly *.puml`
> (không in gì = không có lỗi).

Diagram **kế hoạch** của epic (as-is/to-be, vẽ trước khi code) nằm riêng ở
[`design/*.puml`](design/). **Lưu ý:** `03_to_be_component.puml` vẽ đường
`StrategyEngine → LiveTradingCoordinator` qua event bus — bản vẽ đó là **lịch sử kế hoạch**, đã
bị thay đổi khi triển khai vì lý do an toàn ở §5.4. Diagram trong tài liệu này là **as-built**.

---

## Ba câu hỏi kiểm tra bạn đã "hero" chưa

1. *Vì sao app đọc chart từ mainnet nhưng đặt lệnh ở testnet, và điều đó gây rủi ro gì?*
   → §1.1 + ADR §2. Rủi ro: giá nhìn thấy ≠ giá khớp; `EPIC-021K` phải dựng banner nói ra.
2. *Response của `POST /fapi/v1/order` trả `status: "NEW"` — vì sao app không dùng nó làm trạng
   thái lệnh?*
   → §2.3 + ADR §4. Vì response chỉ nói "đã nhận"; sự thật (khớp một phần, huỷ sau, bị tác nhân
   khác đổi) chỉ đến từ User Data Stream.
3. *Chạy một backtest có thể đặt lệnh thật không?*
   → §5.4. **Trước đây thiết kế cho phép**; đã sửa bằng lời gọi trực tiếp thay vì event bus.
