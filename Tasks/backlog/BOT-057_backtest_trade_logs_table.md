# Nhiệm vụ: Backtest Screen — Bảng Lịch sử Lệnh (Trade Logs Table)

> **Task 4/4** của màn Backtest: [`BOT-022`](BOT-022_backtest_screen_static_ui.md)
> → [`BOT-055`](BOT-055_backtest_performance_metrics_panel.md) →
> [`BOT-056`](BOT-056_backtest_chart_canvas.md) → `BOT-057` (file này).
> Thuộc Epic [BOT-040](BOT-040_backtest_screen_full_feature_epic.md).
> Phụ thuộc [`BOT-022`](BOT-022_backtest_screen_static_ui.md), `BOT-021` ✅;
> phần dòng mở rộng cần [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md).

## 1. Mục tiêu

Bảng lệnh đầy đủ theo mockup: lọc, tìm kiếm, export, phân trang, và **dòng mở
rộng chi tiết** cho từng lệnh.

## 2. Các bước thực hiện (Action Items)

### 2.1 Bảng cơ bản (làm được ngay với `BacktestResult.trades`)

- [ ] `QTableView` với các cột theo mockup:
  - **STT / Tên lệnh** — đánh số ở UI (không thêm field `id` vào `Trade`:
    không có ý nghĩa nghiệp vụ, chỉ để hiển thị). Mockup: "#216 lệnh bán".
  - **Loại** — Vào / Thoát.
  - **Ngày giờ** — `entry_time` / `exit_time`, **xếp chồng 2 tầng trong cùng
    1 row** (theo mockup), không tách 2 dòng.
  - **Giá v/t** — `entry_price` / `exit_price`, cũng 2 tầng.
  - **Quy mô** — `quantity` + giá trị USD tính ở UI (`quantity * entry_price`).
  - **Lãi/Lỗ ròng** — `pnl`, màu theo dấu.
  - **Return %** — `pnl_percent`.
- [ ] Tab lọc: **Tất cả** (kèm tổng số lệnh, mockup: "44 LỆNH") / **Mua
  (LONG)** / **Bán (SHORT)** / **Lệnh thắng** (`pnl > 0`) / **Lệnh thua**
  (`pnl < 0`) — lọc `list[Trade]` ở UI, không cần query mới. Tab SHORT hiển
  thị nhưng **luôn rỗng** cho tới [`BOT-050`](BOT-050_short_selling_support.md)
  (không ẩn, để không phải sửa UI lại sau).
- [ ] Ô tìm kiếm theo mã lệnh / ngày tháng — lọc client-side.
- [ ] Nút **Export** (CSV) từ `list[Trade]`.
- [ ] Phân trang.

### 2.2 Dòng mở rộng chi tiết — cần [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md)

Bấm vào 1 lệnh → xổ ra 3 khối (theo mockup dòng `#216`):

- [ ] **"Lý do vào lệnh (Entry Catalyst)"** — `Trade.entry_reason` (nguồn gốc
  là `Signal.reason`, vd *"QML Liquidity Sweep + EMA 21 Resistance"*).
- [ ] **"Lý do thoát lệnh (Exit Execution)"** — `Trade.exit_reason` (vd *"Chạm
  Stop Loss (SL)"*). Map enum → nhãn tiếng Việt dễ đọc.
- [ ] **"Chỉ số đánh giá & Thời lượng"** — render **động theo key** có trong
  `Trade.metadata` (**không hardcode** "QML Score" — user nêu rõ *"tùy vào
  chiến thuật"*), cộng thời lượng tính từ `exit_time - entry_time`, format
  "4h 00m".
- [ ] UI phải chịu được `metadata` **rỗng hoặc có key lạ** mà không crash —
  đây là cái giá của thiết kế mở, đã chấp nhận có chủ đích ở `BOT-045`.

## 3. Rủi ro / Lưu ý

- 2.1 làm được độc lập; 2.2 bị chặn bởi `BOT-045`. Nếu `BOT-045` chưa xong,
  vẫn ship được 2.1 (bảng đầy đủ, chỉ chưa mở rộng được).
- Dữ liệu có thể lớn (mockup 44 lệnh, thực tế có thể hàng nghìn) — dùng model
  chuẩn của `QTableView`, không dựng list widget thủ công.

## 4. Phụ thuộc

- [`BOT-022`](BOT-022_backtest_screen_static_ui.md) — khung màn hình.
- `BOT-021` ✅ — `Trade`/`BacktestResult`.
- [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md) — **chặn** mục 2.2.
- [`BOT-050`](BOT-050_short_selling_support.md) — dữ liệu cho tab SHORT.
