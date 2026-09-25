# Epic: Quản trị Lệnh Nâng cao & Kiểm soát Rủi ro Backtest (Advanced Order Execution & Risk Management Epic)

**Mã Epic:** `BOT-105`  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** ✅ **Hoàn thành (25/09) — 5/5 cơ chế xong, kể cả Partial TP (`BOT-105C`)**  
**Ưu tiên:** ⚡ **P1 — Tính năng Cốt lõi (Core Trading Simulation)**  
**Liên quan:** [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md), [`BOT-049`](../completed/BOT-049_leverage_and_liquidation.md), [`BOT-050`](../completed/BOT-050_short_selling_support.md), [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md), [`BOT-104`](../completed/BOT-104_backtest_properties_and_broker_simulator_modal.md)

---

## 1. Mục tiêu Epic

Mở rộng năng lực khớp lệnh của `PaperExchange` từ mức cơ bản (vào 100% lệnh thị trường và chỉ đóng khi có tín hiệu ngược) lên tầm **Mô phỏng Giao dịch Chuyên nghiệp** tương đương TradingView / MT5:
1. **Quản trị Rủi ro Tự động**: Hỗ trợ Trailing Stop (bám đỉnh), Break-Even Stop (dời về hòa vốn) và Chốt lời từng phần (Partial TP / Scaling Out).
2. **Khớp lệnh & Phân xử Xung đột Không Thiên lệch (No-Bias Intra-bar Resolution)**: Xử lý triệt để trường hợp nến quét qua cả giá SL lẫn TP bằng dữ liệu Tick 1s (`BOT-076`), không giả định ngây thơ.
3. **Phối hợp với `BOT-104`**: Nhận cấu hình từ `StrategyPropertiesModal.qml` và tích hợp với Position Sizing (% Vốn / Cố định USD).

---

## 2. Danh sách Task thành phần (Sub-tasks)

| Task ID | Tên Nhiệm vụ | Độ phức tạp | Mô tả tóm tắt |
| :--- | :--- | :---: | :--- |
| ✅ **[`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md)** | **Stop Loss / Take Profit Cơ bản & Risk Sizing** | 🔴 `L` | **Xong (19/08).** SL/TP cố định theo %, theo Giá hoặc theo ATR; kiểm tra High/Low từng bar. |
| ✅ **[`BOT-105A`](../completed/BOT-105A_trailing_stop_and_partial_tp.md)** | **Trailing Stop & Break-Even Stop** | 🔴 `L` | **Break-Even (23/09) + Trailing Stop (25/09) xong** — tự động dời SL về Entry khi MFE đạt ngưỡng, và bám đỉnh/đáy giá ratchet dần khi đã kích hoạt. Partial TP tách thành `BOT-105C` riêng — xem file task §3/§4. |
| ✅ **[`BOT-105B`](../completed/BOT-105B_intrabar_magnifier_and_conflict_resolution.md)** | **Intra-bar Bar Magnifier & SL/TP Conflict Resolution** | 🔴 `L` | **Xong (24/09)** — pessimistic SL-first (§2.1) đã có sẵn từ `BOT-041`; phần thật sự mới là Bar Magnifier (§2.2): khi bar tĩnh chạm cả SL và TP, tra klines mịn hơn qua `IMarketDataRepository.get_klines()` để xác định thứ tự chạm thật, lazy (chỉ tra khi thật sự mơ hồ), fallback về pessimistic khi không có dữ liệu. |
| ✅ **[`BOT-105C`](../completed/BOT-105C_partial_take_profit.md)** | **Chốt lời từng phần (Partial Take Profit / Scaling Out)** | 🟡 `M` | **Xong (25/09)** — danh sách mốc `(price_pct, close_fraction)` có thứ tự; mỗi mốc đóng đúng phần đó của khối lượng gốc, sinh `Trade` riêng gắn `ExitReason.PARTIAL_TAKE_PROFIT`, phí/margin được chia tỷ lệ đúng qua các lần đóng một phần liên tiếp. |
| ✅ **[`BOT-049`](../completed/BOT-049_leverage_and_liquidation.md)** | **Đòn bẩy (Leverage), Ký quỹ Isolated & Giá thanh lý** | 🔴 `L` | **Xong (22/09).** Mô phỏng đòn bẩy 1x..50x, tính Liquidation Price chính xác theo chuẩn Binance Futures. |
| ✅ **[`BOT-050`](../completed/BOT-050_short_selling_support.md)** | **Bán khống (Short Selling) & Đảo chiều Vị thế** | 🔴 `L` | **Xong (20/08).** Hỗ trợ mở vị thế SHORT, quản lý PnL khi giá giảm, và lệnh đảo chiều (Reverse). |

---

## 3. Kiến trúc Triển khai (Clean Architecture)

1. **Domain Layer**:
   - `OrderType` (Enum): `MARKET`, `LIMIT`, `STOP_LOSS`, `TAKE_PROFIT`, `TRAILING_STOP`.
   - `Position`: Quản lý danh sách các mốc chốt lời `tp_levels: list[TakeProfitLevel]`, `stop_loss_price`, `trailing_offset_ticks`, `is_breakeven_triggered`.
   - `PaperExchange`: Kiểm tra các điều kiện thoát lệnh trước khi kiểm tra tín hiệu chiến lược mới.
2. **Application Layer**:
   - `RunStaticBacktestCommand` & `RunRealtimeBacktestCommand` nhận cấu hình SL/TP/Trailing.
3. **Presentation Layer**:
   - Tích hợp các trường nhập liệu vào `StrategyPropertiesModal.qml` (`BOT-104`).
