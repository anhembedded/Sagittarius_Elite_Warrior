# ADR — Môi trường sàn và đường đi lệnh (`EPIC-021`)

- **Ngày:** 2026-09-01
- **Trạng thái:** ✅ Approved (user chốt trực tiếp trong phiên lập epic)
- **Phạm vi:** mọi task con của `EPIC-021`, và mọi task tương lai chạm tới việc đặt lệnh

---

## 0. Vì sao cần ADR này trước khi viết dòng code đầu tiên

Hôm nay app **không có khái niệm "môi trường sàn"**. Không phải "có nhưng đặt sai" — là
**không tồn tại**: `PythonBinanceClient` được DI dựng không tham số
([`binance_bot_module.py:231`](../../../src/binance_bot_module.py)), nên nó luôn nối
`https://api.binance.com` ẩn danh, và websocket cũng vậy
(`AsyncClient.create()`, [`binance_websocket_service.py:110`](../../../src/infrastructure/binance/binance_websocket_service.py)).

Thêm testnet vào một hệ thống như vậy **không** phải là thêm một cờ boolean. Nó là thêm một
chiều trạng thái mới mà **mọi** màn hình, mọi query, mọi log phải hiểu đúng — và nếu chiều đó
được cài sai thì hậu quả không phải một widget xấu, mà là một lệnh thật trên tiền thật. Vì vậy
các quyết định dưới đây được chốt trước, bằng văn bản, thay vì để mỗi task con tự suy luận.

---

## 1. Sàn giao dịch: **USD-M Futures Testnet**, không phải Spot Testnet

**Quyết định (user chốt):** đường đặt lệnh của epic này nhắm
`https://testnet.binancefuture.com/fapi` (USD-M Futures), vì user chủ yếu giao dịch futures.

**Lý do kỹ thuật củng cố lựa chọn này — không chỉ là sở thích:** mô hình khớp lệnh của repo đã
là mô hình futures từ lâu. [`PaperExchange`](../../../src/domain/backtesting/paper_exchange.py)
có `PositionSide.SHORT`, `long_leverage`/`short_leverage`
([`broker_simulation_config.py:25-26`](../../../src/domain/value_objects/broker_simulation_config.py)),
`MarginRiskPolicy` tính margin/mark-to-market; `SignalAction` có `SHORT`/`COVER`
([`signal_action.py:17,19`](../../../src/domain/value_objects/signal_action.py)); và
`EmaTrendPullbackStrategy` **đang thật sự phát tín hiệu SHORT**.

Nếu chọn Spot Testnet thì **không short được**, tức là một nửa hành vi mà backtest đã kiểm
chứng sẽ không có đường ra sàn — backtest và live sẽ nói hai ngôn ngữ khác nhau, đúng loại lệch
mà `StrategyEngine` được thiết kế để không bao giờ xảy ra ("batch ≡ incremental",
[`strategy_engine.py`](../../../src/application/services/strategy_engine.py) docstring).

**Cái giá đã chấp nhận:** futures kéo theo position mode (One-way/Hedge), margin type
(Isolated/Cross), leverage theo từng symbol, funding rate, và khả năng bị thanh lý — nhiều bề
mặt sai hơn Spot đáng kể. Epic này xử lý bốn cái đầu **tường minh** (`EPIC-021D`, `EPIC-021E`);
funding rate và thanh lý được ghi nhận là **chưa** mô hình hoá và phải có type/test nói lên điều
đó (§6).

**COIN-M futures và Options nằm ngoài phạm vi.** `python-binance` có sẵn endpoint cho chúng
(`FUTURES_COIN_TESTNET_URL`, `OPTIONS_TESTNET_URL`) — sự tồn tại của endpoint không phải lý do
để hỗ trợ.

---

## 2. Hai lựa chọn độc lập trong Settings: **nguồn dữ liệu** và **nơi đặt lệnh**

**Quyết định (user chốt):** Settings có **hai** lựa chọn riêng, không phải một cờ "testnet"
chung:

| Lựa chọn | Giá trị hợp lệ | Mặc định |
| :--- | :--- | :--- |
| **Nguồn dữ liệu thị trường** (`MarketDataVenue`) | `MAINNET_PUBLIC`, `FUTURES_TESTNET` | `MAINNET_PUBLIC` |
| **Nơi đặt lệnh** (`TradingVenue`) | `DISABLED`, `FUTURES_TESTNET` | `DISABLED` |

**Vì sao phải tách:** hai thứ này trả lời hai câu hỏi khác nhau. Dữ liệu thị trường trả lời
*"chart và backtest của tôi có đáng tin không"*; nơi đặt lệnh trả lời *"tiền của tôi đi đâu"*.
Gộp chúng vào một cờ buộc user phải đánh đổi hai thứ không liên quan: bật testnet để đặt lệnh
an toàn thì đồng thời làm hỏng luôn chart và backtest (testnet có thanh khoản giả, lịch sử
ngắn, tập symbol nhỏ hơn).

### 2.1 Ràng buộc kỹ thuật đã đo, quyết định hình dạng code

`python-binance` có **đúng một** cờ `testnet` trên toàn bộ `Client`, và nó đổi endpoint của
*mọi* nhóm API cùng lúc — spot, futures, futures-data, coin-m, options, và websocket
(`base_client.py:251,274,285,291,302,308`; `streams.py:128-130`). Không có cách nào để một
instance `Client` vừa đọc mainnet vừa đặt lệnh testnet.

**Hệ quả bắt buộc:** hai lựa chọn ở §2 phải được hiện thực bằng **hai instance `Client` riêng
biệt**, không phải hai tham số của một client:

- **Market-data client** — `testnet` theo `MarketDataVenue`, **không key** khi ở
  `MAINNET_PUBLIC` (kline và exchangeInfo là public; gắn key vào đây chỉ tăng bề mặt rò rỉ mà
  không mở thêm khả năng nào).
- **Trading client** — luôn `testnet=True` trong epic này, **có key**, và là instance **duy
  nhất** trong toàn app được phép ký request.

Đây cũng là lý do `ITradingClient` phải là port **riêng**, không phải thêm method vào
`IExchangeClient` (Interface Segregation, `architecture-rule.md` §1): hai port khác nhau vì
chúng nói chuyện với hai kết nối khác nhau, có yêu cầu bảo mật khác nhau — không phải vì "chia
cho gọn".

### 2.2 Tổ hợp lệch nguồn phải kêu, không được im lặng

Tổ hợp `MAINNET_PUBLIC` + `FUTURES_TESTNET` (mặc định sau khi user bật giao dịch) là **hợp lệ và
được khuyến khích**, nhưng nó có một cái bẫy thật: **giá anh nhìn thấy trên chart không phải giá
lệnh của anh khớp.** Testnet futures là một sàn riêng với sổ lệnh riêng.

Vì vậy tổ hợp lệch nguồn **phải** hiện diện trong UI như một cảnh báo thường trực
(`EPIC-021I`), và phải có một type mang đúng ngữ nghĩa đó (`VenueAlignment`) chứ không phải một
dòng chữ hard-code trong widget — theo `architecture-rule.md` §7 ("code phải tự nói lên chính
nó").

**Phát biểu đúng về giá trị của việc chạy testnet với data mainnet:** nó kiểm thử **đường ống**
(ký request, làm tròn khối lượng, vòng đời lệnh, reconciliation, UI) — **không** kiểm thử
**chiến lược**. Số PnL thu được trên testnet **không** phải bằng chứng về edge của chiến lược, và
không được trình bày như thể là.

---

## 3. Giao dịch mainnet **không tồn tại như một lựa chọn** trong epic này

**Quyết định:** `TradingVenue` có **đúng hai** member: `DISABLED` và `FUTURES_TESTNET`. Không có
`MAINNET`. Không có cờ `allow_mainnet=False` để ai đó lật.

**Lý do:** một hằng số cấu hình có thể bị đổi bằng một dòng JSON; một enum member không tồn tại
thì **không có gì để đổi**. Bật giao dịch tiền thật sẽ phải là một epic riêng, mở đúng file
enum này, và khi đó người mở nó buộc phải đọc ADR này. Đây là áp dụng trực tiếp
`architecture-rule.md` §7: quyết định "chưa cho phép mainnet" nằm trong **type**, không nằm
trong tài liệu.

Định hướng đã chốt ở [`ROADMAP.md`](../../ROADMAP.md) — *"Backtest đáng tin trước, giao dịch
thật gác lại"* — **không** bị epic này đảo ngược. `BOT-008` vẫn chưa mở khoá.

---

## 4. Sự thật về lệnh đến từ User Data Stream, không từ response của lệnh

**Quyết định:** trạng thái lệnh/vị thế mà app tin và hiển thị đến từ
`futures_user_socket` (`ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`), không phải từ giá trị trả về của
`futures_create_order`.

**Lý do:** response của lệnh chỉ nói *"sàn đã nhận"*. Một lệnh MARKET có thể khớp một phần, khớp
nhiều mức giá, bị huỷ do thiếu margin, hoặc vị thế bị đổi bởi **một tác nhân khác** (user tự vào
web testnet, một phiên app khác). App **không được** giả định mình là chủ duy nhất của tài
khoản. Đó cũng là lý do `EPIC-021G` bắt buộc có bước reconciliation lúc khởi động
(`futures_position_information`) thay vì tin vào state trong RAM.

Theo `architecture-rule.md` §6, đây là **sự thật của hệ thống** (≥2 màn quan tâm: bảng lệnh, chart
marker, log) → **event bus + đúng một Feed** (`OrderFeed`), không phải Qt signal riêng của một
màn.

---

## 5. Tầng test: testnet là tier **opt-in**, không bao giờ vào `ci-local.ps1 -Full`

**Quyết định:** thêm `tests/testnet/`, chỉ chạy khi có biến môi trường bật + key thật; nằm
**ngoài** cổng `-Full`. Đồng thời mở rộng `tests/sanity/binance_fake_server.py` để phục vụ các
endpoint futures mà epic này dùng, để tầng integration vẫn hoàn toàn tất định.

**Lý do:** `testing-rule.md` §1 đã quy định integration **không bao giờ** phụ thuộc sàn công khai
hay tài khoản sống, và `EPIC-009`'s ADR quy định thay thế chỉ được đặt ở **ranh giới mạng, tại
cấu hình** — chính là lý do fake server tồn tại thay vì một `IExchangeClient` viết tay (thứ đã
sinh ra `BUG-026`/`BUG-027`). Một tier chạm sàn thật là **bằng chứng vận hành**, không phải một
tầng test thứ năm, và không được phép làm đỏ cổng CI của người khác vì key hết hạn.

Key của Futures Testnet **bị reset định kỳ** và là **bộ key riêng**, không dùng chung với Spot
Testnet hay mainnet. Lỗi 401 vì key hết hạn phải được phân biệt rõ với lỗi cấu hình sai
(`EPIC-021D`).

---

## 6. Cái chưa làm, và cách nó phải hiện diện trong code

Theo `architecture-rule.md` §7.1, mỗi thứ dưới đây phải có **type hoặc test** đại diện, không
được chỉ nằm trong ADR này:

| Chưa làm | Phải hiện diện bằng |
| :--- | :--- |
| Funding rate (futures thu/trả 8h/lần) | Test khoá: PnL live **không** trừ funding, kèm lý do và điều kiện gỡ |
| Thanh lý (liquidation) | `MarginRiskPolicy` đã có khái niệm margin; live chỉ *đọc* `liquidationPrice` để hiển thị, có type riêng, không tự tính |
| COIN-M, Options | Không có enum member — cùng cơ chế rào an toàn như §3 |
| Nhiều vị thế/symbol, Hedge mode | `EPIC-021E` chốt One-way mode; Hedge mode phải bị **từ chối tường minh** lúc kiểm tra kết nối, không phải chạy rồi sai |
| Giao dịch mainnet | Không có enum member (§3) |

---

## 7. Cái đã bị bác bỏ, và tại sao

- **Một cờ `testnet: true` trong `app_config.json`.** Bác bỏ: gộp hai câu hỏi độc lập (§2), và
  đặt quyết định "tiền đi đâu" ngang hàng với một tuỳ chọn màu chữ trong cùng một file JSON.
- **Thêm `create_order` vào `IExchangeClient` có sẵn.** Bác bỏ: vi phạm Interface Segregation, và
  buộc mọi test double market-data hiện có phải implement thêm method giao dịch — đúng khuôn
  `BUG-026` (implementer rơi lại sau interface).
- **Dùng `Client.API_URL = ...` như tầng sanity đang làm để trỏ sang testnet.** Bác bỏ: đó là
  monkey-patch một class attribute toàn cục, đúng thứ chỉ chấp nhận được trong một fixture test
  có `try/finally` khôi phục ([`tests/sanity/conftest.py:147,153`](../../../tests/sanity/conftest.py)).
  Trong production, endpoint phải là **tham số dựng client**.
- **Để `MarketTickEventHandler` gọi thẳng trading client.** Bác bỏ: Application layer phát
  command qua dispatcher; adapter sàn nằm ở Infrastructure. Handler đó hiện chỉ `logger.info()`
  và đó là đúng chỗ để **phát `ExecuteOrderCommand`**, không phải chỗ để nối HTTP.
