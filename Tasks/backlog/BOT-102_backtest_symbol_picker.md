# Nhiệm vụ: Backtest screen — thêm cơ chế đổi symbol (hiện đang bị khoá cứng)

> Không thuộc epic nào. Phát hiện khi rà lại `BackTestPresenter` lúc chuẩn bị
> làm [`BOT-076`](../in_progress/BOT-076_realtime_backtest_engine.md) §3.3.
> Không chặn, không bị chặn bởi `BOT-076`.

## 1. Triệu chứng

Màn Backtest không có cách nào đổi cặp giao dịch từ UI. Đã verify trong
[`backtest_presenter.py`](../../src/presentation/ui/screens/backtest/backtest_presenter.py):

```python
self._symbol: str = default_symbols[0] if default_symbols else _FALLBACK_SYMBOL
```

`self._symbol` được set **đúng 1 lần** trong `__init__`, đọc từ
`DEFAULT_SYMBOLS` trong config (`user_config.json` — mặc định
`["BTCUSDT", "ETHUSDT"]`, luôn lấy phần tử đầu tiên) và dùng xuyên suốt cho
mọi lệnh gọi backtest/sync/chart. Không có property, signal, hay modal nào
đọc/ghi giá trị này sau đó — muốn backtest `ETHUSDT` thay vì `BTCUSDT`, cách
duy nhất là sửa thứ tự trong `user_config.json` rồi khởi động lại app.

`render_symbol_cards(symbols: list[str])` (`backtest_view.py`) **đã** nhận
một `list[str]`, không phải 1 symbol cố định — kiến trúc phía dưới sẵn sàng
cho nhiều/đổi symbol, chỉ là Presenter luôn gọi nó với `[self._symbol]` duy
nhất, không có đường nào khác ghi vào `self._symbol`.

Đã kiểm tra: Dashboard screen **cũng không có** cơ chế đổi/thêm symbol lúc
chạy — cùng tình trạng, static từ `DEFAULT_SYMBOLS`. Không có task nào khác
trong repo (backlog/completed) nhắc tới việc này.

## 2. Vì sao đáng làm

Người dùng backtest nhiều cặp khác nhau trong một phiên làm việc bình thường
(so sánh chiến thuật trên `BTCUSDT` vs `ETHUSDT` chẳng hạn) — hiện tại việc
đó đòi hỏi sửa file config + khởi động lại app, không phải trải nghiệm hợp
lý cho một tính năng cốt lõi của màn hình.

## 3. Gợi ý hướng làm (chưa quyết, người nhận task tự chọn)

Màn Backtest đã có đúng khuôn mẫu cho việc này: **Strategy Picker** và
**Timeframe Picker** — cả hai đều là modal + `Signal`/`Property` trên
`BackTestViewModel`, mở qua `openStrategyPickerRequested`/
`openTimeframePickerRequested`, đọc lại qua `selectedStrategyKey`/
`selectedTimeframe`. Một `SymbolPickerModal` đi đúng khuôn mẫu này là lựa
chọn ít rủi ro nhất — không cần phát minh cơ chế mới.

**Câu hỏi thiết kế chưa chốt — cần hỏi user trước khi code, đừng đoán:**
nguồn danh sách symbol để hiển thị trong picker lấy từ đâu? Đã verify: repo
**chưa có** bất kỳ lệnh gọi Binance exchange-info nào để liệt kê toàn bộ cặp
khả dụng trên sàn (`grep` không ra kết quả). Hai hướng khả dĩ:

- **(a) Danh sách tĩnh từ `DEFAULT_SYMBOLS`** trong config — nhanh, không
  cần gọi mạng, nhưng người dùng vẫn phải sửa config để thêm 1 symbol mới
  chưa từng liệt kê.
- **(b) Gọi Binance exchange-info thật** để liệt kê mọi symbol khả dụng —
  đúng nhu cầu hơn nhưng là việc mới hoàn toàn (cần client method mới,
  caching, xử lý lỗi mạng), và có thể trùng lặp với phần market-metadata mà
  [`BOT-095E1`](../completed/BOT-095E1_symbol_market_metadata_validation.md)
  đã xây — đọc lại task đó trước, có thể đã có sẵn hạ tầng gọi exchange-info
  dùng chung được thay vì viết lại.

Sau khi đổi symbol, các chỗ cần cập nhật (chưa đầy đủ, rà lại lúc code):
`self._symbol` trên Presenter, `render_symbol_cards()`, mọi command/query
đang truyền `symbol=self._symbol` cứng, `BacktestRunConfig.symbol` (Dirty
Tracking phải coi đổi symbol là 1 thay đổi thật — xem
`compute_diff_summary()`), và dữ liệu/coverage/database status hiển thị cho
symbol mới (không được lẫn dữ liệu cũ của symbol trước).

## 4. Test bắt buộc

Theo `.agents/rules/code-rule.md` — sanity test cho picker mới (DI + UI), và
ít nhất 1 test xác nhận đổi symbol thật sự thay đổi `self._symbol` trên
Presenter và symbol đó được dùng cho lần backtest/sync kế tiếp (không chỉ
đổi hiển thị mà logic vẫn chạy trên symbol cũ — lớp lỗi B, xem
[Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md)).
