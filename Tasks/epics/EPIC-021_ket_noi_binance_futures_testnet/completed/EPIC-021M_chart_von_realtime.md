# EPIC-021M — Chart vốn (equity) realtime cho màn Giao dịch

- **Trạng thái:** ✅ **Đã xong (2026-09-02)** — xem §6 "Kết quả xây dựng" cho danh sách file thật.
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021I` (cần màn Giao dịch tồn tại để cắm vào) · **Chặn:** —
- **Lập ngày:** 2026-09-02, tách ra từ `EPIC-021I` sau khi user review mockup

---

## 1. Bối cảnh & vấn đề thật

Backtest **đã có** đường vốn: `BacktestResult.equity_curve: list[tuple[datetime, float]]`, cùng
`ChartDisplayMode.EQUITY` và hai hàm dựng sẵn `equity_curve_to_candles()` /
`equity_curve_to_line_data()` ([`chart_canvas_view.py`](../../../src/presentation/ui/screens/backtest/logic/chart_canvas_view.py)).

**Live thì không có gì cả.** Đo bằng `grep`, không suy đoán:

| Cái cần | Trạng thái hôm nay |
| :--- | :--- |
| Chuỗi (thời điểm, vốn) của phiên live | **Không tồn tại** — không có accumulator, không có persistence |
| Số dư tại một thời điểm | Có, nhưng chỉ **ảnh chụp** (`ExchangeConnectionStatus.usdt_balance`, đọc khi bấm Kiểm tra kết nối) |
| Số dư trong `ACCOUNT_UPDATE` | Sàn **có gửi**, nhưng parser đang **vứt đi** |

Dòng vứt đi đó nằm ở
[`user_data_event_parser.py:96`](../../../src/infrastructure/binance/user_data_event_parser.py):

```python
return [position["s"] for position in payload.get("a", {}).get("P", [])]
```

Chỉ đọc `"P"` (positions). Mảng `"B"` (balances) trong cùng payload **chưa ai đọc**.

Không có task này thì đường vốn live hoặc không có, hoặc bị bịa ra từ dữ liệu không phải sự thật —
đúng loại lỗi mà ADR §4 tồn tại để chặn.

## 2. Thiết kế + lý do

### 2.1 Nguồn dữ liệu: `ACCOUNT_UPDATE` stream (user chốt 2026-09-02)

| Phương án | Đánh giá |
| :--- | :--- |
| **Stream `ACCOUNT_UPDATE`** ✅ **chọn** | Không thêm request mạng nào; đúng ADR §4 ("sự thật đến từ User Data Stream"); chỉ lấy mẫu khi có thay đổi thật |
| REST `/fapi/v2/account` định kỳ | Mẫu đều đặn kể cả lúc đứng yên, nhưng thêm request lặp lại + rủi ro rate limit |
| Cả hai (stream + REST nhịp chậm) | Chính xác hơn nhưng phức tạp gấp đôi cho một biểu đồ quan sát — **không** chọn ở vòng này |

**Hệ quả đã chấp nhận:** stream chỉ bắn khi số dư/vị thế đổi, nên đường vốn có **khoảng cách
không đều**. Đây là đặc tính đúng của dữ liệu, không phải khiếm khuyết cần lấp bằng nội suy — vẽ
đúng cái sàn nói, không bịa điểm ở giữa.

### 2.2 Vốn = `walletBalance` + `unrealizedPnL`, tính ở đâu

`ACCOUNT_UPDATE`'s `"a"."B"` mang `walletBalance` (`"wb"`) và cross wallet (`"cw"`) cho từng asset;
`"a"."P"` mang `unrealizedPnL` (`"up"`) cho từng vị thế. Vốn tại thời điểm đó là tổng của hai phần
— **một phép tính domain thuần**, phải test được không cần mạng (`testing-rule.md` §1), nên nó
thuộc `domain/`, không phải nằm trong parser hay trong widget.

### 2.3 Không persist ở vòng này

Đường vốn sống trong RAM theo phiên, mất khi đóng app — cùng nguyên tắc với `TradingSessionState`.
Persist là một quyết định riêng (schema, retention, migration) và không cần cho mốc "nhìn thấy vốn
biến động khi bot chạy". Ghi rõ ở đây để không ai tưởng là quên.

### 2.4 Không dùng lại `chart_canvas_view.py` của backtest

Hai hàm `equity_curve_to_*` nhận `list[tuple[datetime, float]]` — trùng *hình dạng* nhưng nằm trong
`screens/backtest/logic/`. Import chúng từ màn Giao dịch sẽ tái tạo đúng chiều phụ thuộc mà
`EPIC-021L` vừa đảo xong (`BUG-082`). Hai lựa chọn, chốt khi bắt tay:

1. **Trích xuất** hai hàm sang `qml/`/`components/` dùng chung (kèm guard AST đã có sẵn bắt được vi phạm), hoặc
2. **Viết riêng** cho live — hai hàm ngắn, phụ thuộc ngược lại đắt hơn.

Không được chọn phương án thứ ba là "cứ import tạm rồi dọn sau".

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/infrastructure/binance/user_data_event_parser.py` | Thêm hàm đọc `"a"."B"` + `"a"."P"."up"` — **không** đổi hàm `account_update_changed_symbols` đang có |
| `src/domain/trading/equity_sample.py` | **Mới** — value object `(captured_at, wallet_balance, unrealized_pnl)` + `total` |
| `src/application/services/equity_curve_recorder.py` | **Mới** — accumulator trong RAM, có giới hạn số mẫu (không để phình vô hạn) |
| `src/infrastructure/binance/futures_user_data_stream.py` | Nạp mẫu vào recorder khi xử lý `ACCOUNT_UPDATE` |
| `.../ui/screens/trading/` | Panel chart vốn, dùng `ChartCard` như §2.2b của `EPIC-021I` |

## 4. Kiểm thử

- **Unit (parser):** payload `ACCOUNT_UPDATE` thật có nhiều asset → chỉ lấy USDT; payload không có `"B"` → không crash, không sinh mẫu rác.
- **Unit (domain):** `total = wallet_balance + unrealized_pnl`, gồm ca PnL âm.
- **Unit (recorder):** vượt giới hạn số mẫu → bỏ mẫu cũ nhất, không phình bộ nhớ.
- **Unit:** stream nhận `ACCOUNT_UPDATE` → recorder có thêm đúng **một** mẫu.
- **Không** thêm test sanity (`testing-rule.md` §1).

## 5. Mốc chạy được

Chạy `trade-once --live` ở terminal khác trong lúc màn Giao dịch đang mở: đường vốn **nhích một
bước** đúng lúc lệnh khớp, và giá trị khớp với `Số dư USDT khả dụng` ở rail phải. Đứng yên thì
đường vốn **không** sinh điểm mới — bằng chứng nó phản ánh sự kiện thật chứ không phải đồng hồ.

---

## 6. Kết quả xây dựng (2026-09-02)

Đã dựng xong đúng thiết kế §2, đúng bảng file §3 (mở rộng thêm vài file phát sinh khi build). File
thực tế đã ship:

| File | Việc |
| :--- | :--- |
| `src/domain/trading/equity_sample.py` | **Mới** — `EquitySample(captured_at, wallet_balance, unrealized_pnl)` + `total` (phép tính domain §2.2) |
| `src/domain/events/equity_sampled_event.py` | **Mới, phát sinh khi build** — xem §6.1 |
| `src/infrastructure/binance/user_data_event_parser.py` | +`account_update_equity_sample()` — đọc `"a"."B"` (chỉ USDT) + tổng `"a"."P"."up"`; **không** đổi `account_update_changed_symbols` |
| `src/application/services/equity_curve_recorder.py` | **Mới** — `deque(maxlen=5000)`, bỏ mẫu cũ nhất tự động khi đầy |
| `src/infrastructure/binance/futures_user_data_stream.py` | `_handle_account_update()` nạp mẫu vào recorder + phát `EquitySampledEvent`, cùng chỗ đã phát `PositionChangedEvent` |
| `src/presentation/ui/common/equity_feed.py` | **Mới, phát sinh khi build** — xem §6.1 |
| `.../ui/screens/trading/equity_chart_adapter.py` | **Mới** — `EquitySample` → `OhlcCandle`, viết riêng (§2.4 phương án 2), không kéo `screens/backtest/` vào |
| `.../ui/screens/trading/{trading_view,i_trading_view,trading_presenter}.py` | Panel `ChartCard` thứ hai ("Vốn") trong Workspace, dưới 2 bảng — toolbar/volume ẩn (không xoá) vì không có ý nghĩa với dữ liệu không-nến |
| `src/binance_bot_module.py` | Đăng ký `EquityCurveRecorder` làm singleton, truyền vào `FuturesUserDataStream` |
| `scripts/epic021h_user_stream_probe.py` | Sửa lời gọi constructor cho tham số mới (mypy bắt được) |

### 6.1 Phát sinh khi build: `EquitySampledEvent` + `EquityFeed`

Task §3 không liệt kê rõ cơ chế đưa mẫu mới từ `FuturesUserDataStream` (chạy trên thread nền của
`ITaskManager`) sang `TradingPresenter` (main Qt thread) — chỉ nói "nạp mẫu vào recorder". Soát lại
thấy `FuturesUserDataStream` là một singleton hạ tầng, không phải worker riêng của một Presenter,
nên nó **không có** đường Qt signal riêng để chạm thẳng Trading màn (khác `ui_chart_update_signal`
kiểu Dashboard) — chạm `IEventBus` là đường duy nhất, và bất cứ gì đi qua đó tới Presentation đều
cần `QtEventBridge` (`architecture-rule.md` §6, `BUG-031`). Dựng `EquitySampledEvent` + `EquityFeed`
đúng khuôn `OrderFeed` (`EPIC-021H`) — cũng chỉ một subscriber lúc mới dựng, cùng lý do. Không gộp
vào `OrderFeed`: equity là dữ liệu tài khoản, không phải lệnh/vị thế — đúng phạm vi `OrderFeed`'s
docstring tự giới hạn.

### 6.2 Quyết định bố cục — panel riêng, không phải mode toggle

`chart_canvas_view.py`'s `ChartDisplayMode` (Backtest) chuyển đổi **một** chart giữa OHLC/Equity.
Trading màn **không** làm vậy — dựng một `ChartCard` **thứ hai**, cố định, luôn hiện song song với
chart giá, đặt ở Workspace ngay dưới 2 bảng Vị thế/Lệnh chờ. Lý do: vốn là dữ liệu **tài khoản**
(không đổi theo symbol), trong khi chart giá đổi theo symbol người dùng chọn — gộp vào một widget
sẽ làm việc đổi symbol vô tình xoá luôn đường vốn đang xem. Đúng chữ "Panel chart vốn, dùng
ChartCard như §2.2b" của §3 — `ChartCard` dùng lại nguyên vẹn qua API công khai đã có
(`set_chart_type("line")`, `set_volume_visible(False)`, `toolbar.setVisible(False)`), không sửa gì
trong `components/chart_card/`.

### 6.3 Phạm vi đã cắt có chủ đích

- **Mốc chạy được §5's "khớp với Số dư USDT khả dụng ở rail phải"** — rail của màn Giao dịch hiện
  **không** hiển thị số dư USDT (`EPIC-021I` §6.2 đã ghi rõ lý do: không có event nào qua `OrderFeed`
  mang số dư ví, tự gọi `ITradingClient` vi phạm ràng buộc §2.4 — vẫn đúng, `EquitySampledEvent` là
  event mang số dư đầu tiên, nhưng nối nó vào rail là việc khác, ngoài phạm vi task này). Xác minh
  Mốc 2 thực tế nên so trực tiếp giá trị điểm cuối trên chart vốn với `exchange-status`, không phải
  với rail.
- **Không thêm test sanity** — đúng quyết định đã chốt ở §4.

### 6.4 Kiểm thử

- **Unit (domain):** `test_equity_sample.py` (3 test) — `total`, gồm ca PnL âm và bằng 0.
- **Unit (parser):** `TestAccountUpdateEquitySample` trong `test_user_data_event_parser.py` (4
  test) — nhiều asset chỉ lấy USDT, không có `"B"` → `None` không crash, không có `"P"` → PnL 0.
- **Unit (recorder):** `test_equity_curve_recorder.py` (4 test) — rỗng lúc đầu, ghi đúng thứ tự,
  vượt giới hạn bỏ mẫu cũ nhất, `.samples` trả về snapshot chứ không phải view sống.
- **Unit (stream routing):** 2 test mới trong `test_futures_user_data_stream.py` — có `"B"` → ghi
  đúng 1 mẫu vào recorder **và** phát đúng 1 `EquitySampledEvent` cùng dữ liệu; không có `"B"` →
  không ghi gì.
- **Unit (Feed):** `test_equity_feed.py` (2 test) — đúng khuôn `test_order_feed.py`.
- **Unit (adapter):** `test_equity_chart_adapter.py` (3 test) — 1 mẫu → nến phẳng open=high=low=close,
  nhiều mẫu giữ đúng thứ tự, rỗng → danh sách rỗng.
- **Unit (Trading Presenter):** `test_trading_presenter_equity.py` (3 test) — construction với
  recorder rỗng seed chart rỗng, construction với backlog seed đúng toàn bộ, `EquitySampledEvent`
  nối thêm đúng một điểm.
- **Contract:** `ITradingView` mở từ 4 lên 5 member (`equity_chart`) — `test_trading_view_contract.py`
  cập nhật đếm; cả hai chiều (dùng-mà-không-khai-báo / khai-báo-mà-không-dùng) vẫn xanh.
- Toàn bộ `ruff check`/`ruff format --check` sạch; `mypy` (`src` + `scripts`) bắt đúng 1 lỗi thật
  (`scripts/epic021h_user_stream_probe.py` gọi constructor thiếu tham số mới) — đã sửa, sạch lại;
  cổng CI bắt buộc (`pwsh -NoProfile -File scripts/ci-local.ps1 -Full`) chạy xanh.
