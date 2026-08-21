# BUG-032 — Chart tự động vẽ nến và volume khi chưa nhấn "Chạy Backtest"

**Reported date:** 2026-08-22
**Severity:** 🟡 **P2** (Trải nghiệm người dùng / Hành vi hiển thị dữ liệu)
**Status:** Open

---

## 1. Hiện tượng (Symptom)

Khi người dùng mở màn hình **Backtest Engine** hoặc chọn đổi sang một Symbol khác (ví dụ: `ETHUSDT`) trên thanh công cụ:
- Nút **"CHẠY BACKTEST"** chưa được bấm (bảng Trade Logs bên dưới vẫn ở trạng thái rỗng `0 LỆNH`, "Chưa có dữ liệu lệnh giao dịch").
- Trên giao diện xuất hiện banner cảnh báo thiếu nến (`Thiếu nến từ 2026-08-21 17:58 UTC.`) kèm nút `Đồng bộ dữ liệu ngay`.
- Tuy nhiên, vùng biểu đồ chính (Live Chart) đã tự động thực thi query nến lịch sử và render đầy đủ đồ thị nến (candlesticks) cùng volume bars của symbol đó trước khi bất kỳ lệnh backtest nào được chạy.

### Bằng chứng Log thực tế (Captured Log Evidence)

```text
2026-08-22 01:12:28,085 - App - DEBUG - [PresenterManager] Lazy Loading Screen: backtest
2026-08-22 01:12:28,122 - App.BacktestChartHostFactory - INFO - Backtest chart host initialized for symbol 'BTCUSDT' with backend 'native' (requested: 'auto').
2026-08-22 01:12:28,281 - App - DEBUG - [PresenterManager] Successfully booted backtest (True Lazy Load)
2026-08-22 01:12:28,281 - App - DEBUG - [PresenterManager] Navigating to backtest
2026-08-22 01:12:31,306 - App - INFO - Executing query: ListAvailableSymbolsQuery
2026-08-22 01:12:31,307 - App - DEBUG - Payload: ListAvailableSymbolsQuery()
2026-08-22 01:12:31,571 - App.QueryHandler - DEBUG - Handling ListAvailableSymbolsQuery
2026-08-22 01:12:32,097 - App.QueryHandler - INFO - Fetched 1354 tradeable symbols from the exchange.
2026-08-22 01:12:32,097 - App - DEBUG - ListAvailableSymbolsQuery completed successfully.
2026-08-22 01:12:44,199 - App.BacktestChartHostFactory - INFO - Backtest chart host initialized for symbol 'ETHUSDT' with backend 'native' (requested: 'auto').
2026-08-22 01:12:44,202 - App - INFO - Executing query: GetHistoricalKlinesQuery
2026-08-22 01:12:44,202 - App - DEBUG - Payload: GetHistoricalKlinesQuery(symbol='ETHUSDT', interval='1m', limit=200000, start_time=None, end_time=datetime.datetime(2026, 8, 21, 18, 12, 44, 201967, tzinfo=datetime.timezone.utc), order_by_desc=True)
2026-08-22 01:12:44,202 - App.QueryHandler - INFO - BACKTEST_TRACE action=query_execute_start symbol='ETHUSDT' timeframe='1m' limit=200000 start=None end=datetime.datetime(2026, 8, 21, 18, 12, 44, 201967, tzinfo=datetime.timezone.utc) order_by_desc=True
2026-08-22 01:12:44,202 - App.QueryHandler - DEBUG - Handling GetHistoricalKlinesQuery for ETHUSDT at 1m (limit=200000)
2026-08-22 01:12:44,290 - App.Database - INFO - Created dedicated database for symbol ETHUSDT at Sagittarius_Elite_Warrior\database\ETHUSDT.db
2026-08-22 01:12:44,422 - App.QueryHandler - INFO - BACKTEST_TRACE action=query_execute_complete symbol='ETHUSDT' rows=10098
2026-08-22 01:12:44,422 - App - DEBUG - GetHistoricalKlinesQuery completed successfully.
2026-08-22 01:12:44,423 - App - INFO - Executing query: GetBacktestRangeCoverageQuery
2026-08-22 01:12:44,423 - App - DEBUG - Payload: GetBacktestRangeCoverageQuery(symbol='ETHUSDT', interval='1m', start_time=None, end_time=datetime.datetime(2026, 8, 21, 18, 12, 44, 201967, tzinfo=datetime.timezone.utc), now=datetime.datetime(2026, 8, 21, 18, 12, 44, 201967, tzinfo=datetime.timezone.utc))
2026-08-22 01:12:44,442 - App - DEBUG - GetBacktestRangeCoverageQuery completed successfully.
```

---

## 2. Kỳ vọng (Expected Behavior)

- Khi mới mở màn hình Backtest hoặc khi đổi cấu hình/symbol trên toolbar mà **chưa nhấn "CHẠY BACKTEST"**:
  - Cần xác định rõ hành vi nghiệp vụ mong muốn:
    - **Lựa chọn A (Preview Mode):** Biểu đồ chỉ hiển thị khung trống / empty placeholder với thông báo hướng dẫn hoặc chỉ kiểm tra phạm vi dữ liệu (`GetBacktestRangeCoverageQuery`), không tự động tải và vẽ toàn bộ nến khi chưa có phiên backtest.
    - **Lựa chọn B (Kèm trạng thái rõ ràng):** Nếu chủ đích là tính năng "Preview KLines" để người dùng xem trước đồ thị giá thì cần có nhãn hoặc trạng thái phân biệt rõ ràng giữa "Đồ thị xem trước (Chưa Backtest)" và "Kết quả Backtest (Có điểm Vào/Ra lệnh)".

---

## 3. Các bước tiếp theo (Suggested Next Steps)

1. Thảo luận và thống nhất thiết kế UX cho trạng thái ban đầu của biểu đồ Backtest trước khi chạy mô phỏng.
2. Kiểm tra logic kích hoạt `_request_chart_preview()` trong `BacktestPresenter` khi thay đổi cấu hình (`_on_symbol_changed`, `_on_timeframe_changed`, `_on_time_range_changed`).
3. Viết regression test và cập nhật lại luồng hiển thị nếu cần thay đổi.
