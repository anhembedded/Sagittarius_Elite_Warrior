# BOT-096 — Backtest: Marker/Icon thoát LONG trung thực

**Ưu tiên:** P1 — product-truth / ngăn người dùng diễn giải sai kết quả backtest  
**Phụ thuộc:** `BOT-056` ✅, `BOT-057` ✅  
**Trạng thái:** ✅ Completed

---

## 1. Vấn đề thực tế & Giải pháp

Trong Backtest trước đây, khi `PaperExchange` (long-only) đóng vị thế, biểu đồ vẽ marker entry/exit với cặp nhãn chung `Buy` / `Sell` và tab lọc có `Bán (SHORT)`. Điều này khiến người dùng có cơ sở hợp lý để hiểu nhầm marker đỏ `Sell` là một lệnh SHORT đã khớp, dù bot chưa hề mở short position.

### Các thay đổi đã triển khai:
1. **Domain Marker Semantics (`TradeMarkerType`)**:
   - Thêm enum `TradeMarkerType` (`LONG_ENTRY`, `LONG_EXIT`, `SHORT_ENTRY`, `SHORT_EXIT`).
   - Marker vào lệnh long: `_LONG_ENTRY_LABEL = "MUA (LONG)"` (màu xanh lá BULL_COLOR, mũi tên hướng lên).
   - Marker đóng lệnh long: `_LONG_EXIT_LABEL = "ĐÓNG LONG"` (màu đỏ BEAR_COLOR, mũi tên hướng xuống), **tuyệt đối không dùng "Sell" hay "Short"**.
2. **Trade Logs Table UI (`BackTestTradeLogs.qml`)**:
   - Cập nhật nhãn tab: `"Bán (SHORT) [Chưa hỗ trợ]"`.
   - Cập nhật empty state khi chọn tab SHORT: `"Chế độ bán khống (SHORT) chưa được hỗ trợ trong engine hiện tại (Đang phát triển theo BOT-050)"`.
3. **Regression Tests**:
   - `tests/unit/presentation/ui/screens/test_chart_canvas_view.py`: Xác nhận nhãn `MUA (LONG)` và `ĐÓNG LONG`, assert exit marker không chứa `"SELL"` hoặc `"SHORT"`.
   - `tests/unit/presentation/ui/screens/test_truthful_backtest_markers_and_logs.py`: Kiểm thử toàn diện tính trung thực của execution markers và tab filter.

---

## 2. Kết quả kiểm thử CI
- **Ruff Lint & Format**: 100% Passed.
- **Unit & Integration Tests**: 934 passed (100%).
- **Sanity Tests**: 25 passed (100%).
- **Code Coverage**: 93.94% (vượt ngưỡng yêu cầu 80%).
