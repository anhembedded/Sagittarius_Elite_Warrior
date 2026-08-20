# Nhiệm vụ: Trực Quan Hóa Biểu Đồ & Kiểm Thử Đối Soát Backtest (BOT-111)

**Mã Task:** `BOT-111`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ **Hoàn thành (2026-08-20)**  
**Thuộc Epic:** [`BOT-109`](BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md) (Chuẩn Tham Chiếu Vàng)  
**Phụ thuộc:** [`BOT-110`](../completed/BOT-110_ema_trend_confirm_pullback_strategy.md) ✅

---

## 1. Mục Tiêu

Hoàn thiện hiển thị trực quan cho chiến lược *"EMA Trend Confirm + Pullback + TP%"* trên biểu đồ Backtest (`ChartCard` / Native Chart) và bảng lịch sử lệnh (`TradeLogsTable`), bảo đảm trải nghiệm quan sát số liệu chân thực như TradingView.

---

## 2. Các Hạng Mục Công Việc

1. [x] **Hiển thị Đường Chỉ Báo (Indicator Lines)**:
   - [x] Đường EMA dài (200) màu đỏ (`#f6465d`), độ dày 2.
   - [x] Đường EMA vào lệnh (50) màu xanh dương (`#2962ff`), độ dày 1.
   - → `BaseStrategy.chart_line_colors()`/`chart_line_widths()` mới (optional
     hook, mặc định `{}` — mọi strategy cũ không đổi hành vi), override trong
     `EmaTrendPullbackStrategy`. Thread qua toàn bộ chuỗi:
     `assign_strategy_line_colors()` (ưu tiên override, không lệch palette
     slot cho các line không override) → `_chartStrategyLineSignal` (thêm
     tham số `width`, kiểu Qt `int`) → `IBacktestChartHost.add_overlay_indicator()`
     (port + cả 2 impl Python/Native) → `IndicatorManager.add_overlay()` →
     `pg.mkPen(width=...)`. **Native chart**: nhận `width` cho khớp chữ ký port
     nhưng không áp dụng — ABI indicator series không có trường width (chỉ
     rgba+x/y), viền hạn chế đã ghi chú tại chỗ, không phải bug.
2. [x] **Hiển thị Trade Markers**:
   - [x] Long Entry: "MUA (LONG)", tam giác lên, xanh lá (`BULL_COLOR`).
   - [x] Short Entry: "BÁN (SHORT)", tam giác xuống, đỏ (`BEAR_COLOR`) — trước
     đây `trade_flag_markers()` chỉ vẽ Long dù `Trade.side` đã có từ
     `BOT-050`; `native_backtest_chart_adapter.py` **đã sẵn** mapping cho
     label này từ trước nhưng chưa bao giờ có ai emit nó — dead code, giờ
     mới thật sự chạy.
   - [x] Exit TP: marker vàng (`TAKE_PROFIT_COLOR = "#F3BA2F"`, khớp
     `Palette.ACCENT`), label `"ĐÓNG LONG (TP)"`/`"ĐÓNG SHORT (TP)"`.
     **Lệch nhẹ so với spec gốc** (`text="TP 2.0%"`, số % động): nhúng % thật
     vào label sẽ phá dispatch-theo-chuỗi-cố-định của native adapter
     (`build_native_marker` raise `ValueError` cho label lạ — mọi lệnh TP với
     % khác nhau sẽ crash native chart). Chọn label cố định thay vì % động —
     đã cân nhắc kỹ, xem docstring `_exit_marker()`.
   - [x] Exit khác TP (chạm EMA, hoặc bất kỳ lý do nào khác): **giữ nguyên
     label chung** "ĐÓNG LONG"/"ĐÓNG SHORT" (không thêm hậu tố "(EMA)") —
     quyết định có chủ đích: `ExitReason.STRATEGY_SIGNAL` không có nghĩa
     "chạm EMA" cho MỌI strategy, chỉ đúng cho riêng `EmaTrendPullbackStrategy`
     — thêm hậu tố cứng sẽ sai sự thật (Truthful UI) cho các strategy khác
     dùng chung hàm này.
3. [x] **Bảng Lịch Sử Lệnh (Trade Logs Table)**:
   - [x] Bỏ tag "[Chưa hỗ trợ]" khỏi tab "Bán (SHORT)" + sửa empty-state
     message sai (2 dòng QML) — `trade_log_filter.py`/`trade_log_row.py` đã
     lọc/hiển thị đúng LONG/SHORT từ `BOT-050`, chỉ còn text cũ.
   - [x] Màu PnL/Return% — đã đúng từ trước (`pnl >= 0` quyết định màu, không
     phụ thuộc side) — chỉ verify, không cần sửa code.
4. [x] **Kiểm thử Toàn Diện**:
   - [x] 20 test mới (unit + 1 end-to-end thật qua `RunStaticBacktestCommandHandler`
     + `EmaTrendPullbackStrategy` thật, không mock strategy/handler) + pin DI
     sanity mới xác nhận `"ema_trend_confirm_pullback"` resolve qua container
     thật. Toàn bộ 1494 test `tests/unit/` + 40 sanity cũ giữ nguyên
     (2 test cũ **phải sửa** vì hành vi thật đã đổi — width giờ luôn được
     forward tường minh — không phải làm yếu test, xem commit).
   - [ ] `.\scripts\ci-local.ps1 -Full` — máy này là Linux, không chạy được
     script PowerShell; đã chạy tương đương thủ công (`ruff check`/`format`
     + full pytest suite) đều xanh. Cần chạy lại đúng script trên Windows để
     đóng dấu tick cuối cùng này.
