# Nhiệm vụ: Backtest — Cửa sổ Đặc tính Chiến lược & Mô phỏng Nhà môi giới (Strategy Properties & Broker Simulator Dialog)

**Mã Task:** `BOT-104`  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Liên quan:** [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md), [`BOT-049`](BOT-049_leverage_and_liquidation.md), [`BOT-050`](BOT-050_short_selling_support.md), [`BOT-074`](../completed/BOT-074_execution_trigger_rule_inverted_lock.md), [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md), [`BOT-077`](BOT-077_calc_on_order_fills.md), [`BOT-095B`](../completed/BOT-095B_backtest_fsm_dirty_tracking.md)

---

## 1. Bối cảnh & Vấn đề hiện tại (Gap Analysis)

Hiện tại, các thông số cấu hình Backtest trên thanh Toolbar đang bị **chia cắt manh mún** thành nhiều nút/modal rời rạc và **thiếu vắng các tham số thực tế quan trọng** mà các nền tảng chuẩn mực như TradingView đều cung cấp:

1. **Phân mảnh giao diện (UI Fragmentation)**:
   - Người dùng phải bấm vào nút Vốn (`CapitalDialog.qml`) để chỉnh tiền ban đầu.
   - Bấm vào nút Tập lệnh (`OrderExecutionModal.qml`) để chỉnh chế độ nến đóng / tick.
   - Bấm vào nút Thông số (`BotParamsDialog.qml`) để chỉnh tham số chiến lược (`input_int`, `input_float`).
   - Chưa có một cửa sổ tập trung chuẩn mực (như hộp thoại *Strategy Properties* của TradingView) chứa đầy đủ các tab: **Các đầu vào (Inputs)**, **Đặc tính (Properties)**, **Khớp lệnh (Execution)** và **Mô phỏng Môi giới (Broker Simulator)**.

2. **Thiếu sót nghiêm trọng trong Engine mô phỏng (`PaperExchange`)**:
   - **Quy mô vị thế (Position Sizing)**: Hiện tại luôn bắt buộc All-in 100% balance (`quantity = balance / price`). Thiếu các chế độ:
     - `% Vốn (Percent of Equity)`: ví dụ đi lệnh 10%, 20% vốn.
     - `Cố định USD (Fixed Notional)`: ví dụ mỗi lệnh cố định $1,000.
     - `Cố định Khối lượng (Fixed Contracts / Lots)`: ví dụ mỗi lệnh 0.5 BTC.
   - **Kim tự tháp (Pyramiding)**: `PaperExchange` hiện đang chặn cứng `if self._position is not None: return` (chỉ cho mở duy nhất 1 lệnh). Thiếu cơ chế nhồi lệnh / DCA (cho phép mở tối đa $N$ vị thế cùng chiều).
   - **Trượt giá (Slippage)**: Hiện tại trượt giá mặc định = 0. Không có mô phỏng trượt giá cho các lệnh thị trường (Market orders) khi thanh khoản biến động mạnh.
   - **Hoa hồng & Phí (Commission Model)**: Mới chỉ có taker fee % cố định, chưa hỗ trợ Maker/Taker riêng biệt hoặc phí cố định theo lệnh.
   - **Đòn bẩy & Bán khống (Leverage & Margin)**: Mặc định 1x Spot Long-only. Chưa cấu hình được đòn bẩy Long/Short độc lập.
   - **Quy tắc khớp lệnh Limit & Độ trễ (Order Fill Assumptions & Latency)**: Chưa cấu hình được khớp khi giá chạm (Touch) hay vượt qua (Penetrate), độ trễ 0-tick vs 1-tick delay.

---

## 2. Thiết kế Đề xuất: Hộp thoại Đặc tính Backtest Chuẩn mực (TradingView-Style Modal)

Thiết kế một Modal đa Tab hiện đại (`StrategyPropertiesModal.qml`) hoặc gom nhóm có tổ chức trong hệ thống Modal của màn Backtest:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ EMA Trend Confirm + Pullback + TP%                                  [X] │
├─────────────────────────────────────────────────────────────────────────┤
│ [ Các đầu vào ]  [★ Đặc tính ]  [ Khớp lệnh & Chi tiết ]  [ Môi giới ]  │
├─────────────────────────────────────────────────────────────────────────┤
│ GENERAL (CÀI ĐẶT CHUNG & VỐN)                                           │
│  Vốn ban đầu:            [ 2,000       ]  [ USD        ▼ ]  ⓘ           │
│  Kích thước lệnh m.định: [ 20          ]  [ % of equity ▼ ]  ⓘ           │
│  Kim tự tháp (Pyramiding):[ 4           ]  ⓘ                             │
│                                                                         │
│ MỨC ĐỘ CHI TIẾT VÀ KHỚP LỆNH                                            │
│  Chi tiết hóa thanh giá: [ Mặc định (Theo nến đóng)   ▼ ]  🛈           │
│  Thực thi tập lệnh:      [ On bar close, Khi lệnh khớp ▼ ]  🛈           │
│                                                                         │
│ TRÌNH MÔ PHỎNG NHÀ MÔI GIỚI (BROKER SIMULATOR)                          │
│  Hoa hồng (Commission):  [ 0.01        ]  [ Percent    ▼ ]  ⓘ           │
│  Đòn bẩy vị thế Mua:     [ 1x          ]  ⓘ                             │
│  Đòn bẩy vị thế Bán:     [ 1x          ]  ⓘ                             │
│  Trượt giá (Slippage):   [ 0           ]  ticks             ⓘ           │
│  Khớp lệnh giới hạn:     [ Giá yêu cầu (Touch)         ▼ ]  ⓘ           │
│  Độ trễ thực hiện lệnh:  [ Một tick (1-bar delay)      ▼ ]  ⓘ           │
├─────────────────────────────────────────────────────────────────────────┤
│ [ Mặc định ▼ ]                                     [ Hủy bỏ ]  [ Đồng ý ]│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Kiến trúc Chi tiết 4 Lớp (Clean Architecture)

### A. Domain Layer (Pure Python)
1. **Value Objects**:
   - `PositionSizingType` (Enum): `PERCENT_OF_EQUITY`, `FIXED_CASH`, `FIXED_CONTRACTS`.
   - `PositionSizing` (Dataclass): `type: PositionSizingType`, `value: float`.
   - `CommissionType` (Enum): `PERCENT`, `CASH_PER_ORDER`, `CASH_PER_CONTRACT`.
   - `LimitOrderFillRule` (Enum): `TOUCH_PRICE`, `PENETRATE_PRICE`.
   - `BrokerSimulationConfig` (Dataclass):
     - `slippage_ticks: int = 0` (hoặc `slippage_percent: float = 0.0`)
     - `commission_type: CommissionType = CommissionType.PERCENT`
     - `commission_value: float = 0.001` (0.1%)
     - `long_leverage: float = 1.0`
     - `short_leverage: float = 1.0`
     - `pyramiding: int = 1` (số lệnh cùng chiều tối đa)
     - `limit_fill_rule: LimitOrderFillRule = LimitOrderFillRule.TOUCH_PRICE`

2. **Mở rộng `PaperExchange`**:
   - Hỗ trợ `PositionSizing`: tính `quantity` dựa theo `% of equity` hoặc số tiền cố định thay vì ép 100% balance.
   - Hỗ trợ `pyramiding`: quản lý danh sách `_open_positions: list[_OpenPosition]` (cho phép mở tối đa `pyramiding` vị thế, đóng FIFO hoặc Average Price khi có tín hiệu Exit).
   - Hỗ trợ `slippage`: điều chỉnh giá khớp Market Order: `fill_price = price * (1 + slippage)` cho BUY và `price * (1 - slippage)` cho SELL.

### B. Application Layer (Use Cases & CQRS)
1. **Cập nhật `RunStaticBacktestCommand` & `RunRealtimeBacktestCommand`**:
   - Bổ sung `position_sizing: PositionSizing = PositionSizing(PositionSizingType.PERCENT_OF_EQUITY, 100.0)`.
   - Bổ sung `broker_config: BrokerSimulationConfig = BrokerSimulationConfig()`.
2. **Cập nhật `BacktestRunConfig` & FSM Dirty Tracking**:
   - Đưa các trường mới vào `BacktestRunConfig` immutable snapshot.
   - Mở rộng `compute_diff_summary()` để hiển thị chính xác khi người dùng thay đổi:
     - `Kích thước lệnh (100% → 20% equity)`
     - `Kim tự tháp (1 → 4)`
     - `Trượt giá (0 → 2 ticks)`
     - `Hoa hồng (0.1% → 0.05%)`

### C. Presentation Layer (MVP & QML)
1. **`BackTestViewModel`**:
   - Thêm các thuộc tính & signal phản ứng cho các thông số Đặc tính:
     - `positionSizingType`, `positionSizingValue`
     - `pyramidingLimit`
     - `slippageTicks`
     - `commissionRate`, `commissionType`
     - `longLeverage`, `shortLeverage`
2. **`BackTestPresenter`**:
   - Đọc/ghi cấu hình tập trung từ `user_config.json` hoặc lưu per-strategy.
   - Build `BacktestRunConfig` đầy đủ các trường mới.
3. **QML Component**:
   - Xây dựng `StrategyPropertiesModal.qml` (có thể thay thế hoặc bao bọc `BotParamsDialog.qml` + `OrderExecutionModal.qml` + `CapitalDialog.qml` thành 1 TabView đồng nhất).
   - Đảm bảo tuân thủ `qml-rule.md`: không hardcode kích thước, reactive bindings, micro-animations, text PlainText.

---

## 4. Kế hoạch Triển khai từng Giai đoạn (Phased Roadmap)

* **Phase 1: Domain Core & Simulator Math (Engine First)**
  - Mở rộng `PaperExchange` với Position Sizing (% Equity / Fixed USD / Fixed Coin).
  - Thêm xử lý `pyramiding` (nhiều vị thế con, FIFO/Average exit PnL).
  - Thêm mô phỏng `slippage` và `commission` linh hoạt.
  - Viết 100% Unit test bao phủ các ca biên (vốn không đủ mở lệnh tiếp theo, trượt giá vượt mức, v.v.).

* **Phase 2: Application CQRS & FSM Dirty Tracking**
  - Mở rộng `RunStaticBacktestCommand`, `RunRealtimeBacktestCommand`, `BacktestRunConfig`.
  - Cập nhật `compute_diff_summary()` để Dirty Tracking báo diff chính xác.
  - Cập nhật `BackTestPresenter` thu thập đầy đủ input.

* **Phase 3: QML Tabbed Properties Modal & UI Polish**
  - Xây dựng `StrategyPropertiesModal.qml` với 4 Tab trực quan chuẩn TradingView.
  - Tích hợp vào Toolbar Backtest.
  - Test Sanity, QML Layout responsive, và Integration Test luồng mở/đóng/lưu/chạy lại.

---

## 5. Tiêu chí Nghiệm thu (Acceptance Criteria)

1. **Tính toán chính xác (Financial Invariants)**:
   - Khi chọn `20% of equity`, mỗi lệnh chỉ dùng 20% vốn khả dụng; các vị thế không vượt quá vốn còn lại.
   - Khi `pyramiding = 4`, chiến thuật bắn 4 tín hiệu BUY liên tiếp sẽ mở 4 vị thế con; tín hiệu thứ 5 bị bỏ qua; khi SELL sẽ đóng toàn bộ và tính PnL trung thực.
   - Khi `slippage = 5 ticks`, giá khớp vào lệnh mua cao hơn giá nến và giá bán thấp hơn giá nến đúng 5 ticks.
2. **Giao diện & Trải nghiệm (UI/UX)**:
   - Người dùng có thể xem và chỉnh sửa tất cả thông số trong 1 Modal duy nhất có tabs rõ ràng.
   - Thay đổi bất kỳ thông số nào cũng kích hoạt FSM Dirty Tracking (`isConfigDirty = True`) và hiện Amber Banner giải thích đúng trường đã thay đổi.
3. **Chất lượng mã nguồn**:
   - Đạt 100% pass trên `ci-local.ps1 -Full`.
   - Không vi phạm Clean Architecture / Layer boundaries.
   - Có đầy đủ Unit test cho Domain, Sanity test cho QML Modal, và Integration test cho Presenter.
