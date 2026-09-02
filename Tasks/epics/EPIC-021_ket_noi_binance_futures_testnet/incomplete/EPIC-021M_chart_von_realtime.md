# EPIC-021M — Chart vốn (equity) realtime cho màn Giao dịch

- **Trạng thái:** 🔴 Chưa bắt đầu
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
