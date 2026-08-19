# Nhiệm vụ: Modal "Cấu hình Thông số Bot" — dựng form động từ schema

> Thuộc [Epic BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 3/4** nhóm "hệ thống tham số": [`BOT-044`](BOT-044_param_schema_core.md)
> → [`BOT-046`](BOT-046_strategy_param_plumbing.md) → `BOT-047` (file này) →
> [`BOT-048`](BOT-048_migrate_default_scripts_to_inputs.md).
> Phụ thuộc `BOT-044`, `BOT-046`.

## 1. Mục tiêu

Modal QML dựng form **động** từ schema mà strategy/indicator khai báo — không
hardcode field cho từng chiến lược. Thêm 1 chiến lược mới có tham số lạ thì
modal tự hiện đúng field, **không phải sửa UI**.

## 2. Mockup tham chiếu (user cung cấp)

Tiêu đề: *"CẤU HÌNH THÔNG SỐ BOT: 4 EMA PULLBACK + SIDEWAYS FILTER + QML"* —
tiêu đề lấy từ tên chiến lược đang chọn.

| Field | Widget cần | Nhóm |
| :--- | :--- | :--- |
| Stop Loss (SL %) = 1.2 | float | Quản lý Rủi ro & Đòn bẩy |
| Take Profit (TP %) = 3.2 | float | Quản lý Rủi ro & Đòn bẩy |
| Đòn bẩy = "5x Futures" | **dropdown** (string + options) | Quản lý Rủi ro & Đòn bẩy |
| Rủi ro mỗi lệnh (% Vốn) = 2 | float | Quản lý Rủi ro & Đòn bẩy |
| EMA Fast / Slow = 8 / 21 | int × 2 (cùng 1 hàng) | Chỉ số Kỹ thuật & Độ nhạy QML |
| Độ nhạy Mẫu hình QML (Score %) = 85 | float (0-100) | Chỉ số Kỹ thuật & Độ nhạy QML |

Nút: **"Khôi phục Mặc định"** (trái) · **"Hủy"** · **"Lưu & Re-Backtest"**.

## 3. Các bước thực hiện (Action Items)

- [ ] Component QML dựng widget theo kiểu trong schema: int/float → ô nhập số
  (kèm `suffix` nếu có: `%`, `x`), bool → `StyledCheck` (đã có sẵn), string +
  `options` → dropdown.
- [ ] Gom field theo `group`, mỗi nhóm 1 card có tiêu đề + icon — tái sử dụng
  `BaseCard`/`FieldBackground` đã có (`sagittarius_engine.pyside_mvc`), không
  dựng style mới.
- [ ] "Khôi phục Mặc định" — đọc `default` từ schema, không phải giá trị
  hardcode ở UI.
- [ ] "Lưu & Re-Backtest" — thu giá trị → tạo instance mới với `params` →
  dispatch lại `RunStaticBacktestCommand`.
- [ ] Hiển thị lỗi validate từ domain (`BOT-044` raise khi ngoài min/max) một
  cách rõ ràng tại field, **không nuốt lỗi** — theo `.agents/rules/testing.md`.
- [ ] Ghép 2 nguồn schema vào cùng 1 modal (xem mục 4) nếu quyết định là
  hướng (a).
- [ ] Unit test: schema giả lập với đủ 4 kiểu widget → form dựng đúng số
  field/đúng nhóm; bấm "Khôi phục Mặc định" → giá trị về default; nhập ngoài
  min/max → hiện lỗi, không dispatch.

## 4. ❓ Cần chốt: SL/TP/Leverage/Risk% thuộc về ai?

Trong mockup 4 field này nằm **cùng modal** với EMA period. Nhưng về kiến trúc
chúng là cấu hình **`PaperExchange`** ([`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md),
[`BOT-049`](../backlog/BOT-049_leverage_and_liquidation.md)), không phải của strategy —
`IStrategy` theo đặc tả là hàm thuần của `context`, không biết gì về vốn/vị thế.

- **(a)** `PaperExchange` có schema riêng, UI ghép 2 nguồn vào 1 modal — đúng
  kiến trúc, UI chịu phần ghép. **Khuyến nghị.**
- **(b)** Strategy tự khai báo cả SL/TP (như Pine `strategy()` cho phép) —
  nhưng phá tính thuần của `IStrategy`.

Không tự quyết — xác nhận với user khi bắt đầu task này.

## 5. Phụ thuộc

- [`BOT-044`](BOT-044_param_schema_core.md) — schema (nguồn dữ liệu để dựng form).
- [`BOT-046`](BOT-046_strategy_param_plumbing.md) — đường truyền `params` xuống
  strategy để "Lưu & Re-Backtest" có tác dụng thật.
- [`BOT-022`](BOT-022_backtest_screen_static_ui.md) — màn Backtest là nơi đặt
  nút mở modal này.
- `BOT-016` ✅ / `BOT-030` ✅ — icon Lucide, hạ tầng QML dùng chung.
