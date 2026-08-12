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

### 2.1 Bảng cơ bản (làm được ngay với `BacktestResult.trades`) ✅

- [x] `QTableView` với các cột theo mockup — làm bằng QML `ListView` (đã
  đúng convention Backtest, không phải `QTableView` QtWidgets — panel này
  vốn đã là QML từ `BOT-022`; xem `trade_log_row.py`):
  - **STT / Tên lệnh** — đánh số ở UI (`TradeLogRow.index`, 1-based, ổn định
    qua filter/search/trang — không thêm field `id` vào `Trade`).
  - **Loại** — Vào / Thoát (nhãn tĩnh, engine long-only).
  - **Ngày giờ** — `entry_time` / `exit_time`, xếp chồng 2 tầng trong 1 row.
  - **Giá v/t** — `entry_price` / `exit_price`, cũng 2 tầng.
  - **Quy mô** — `quantity` + giá trị USD tính ở UI (`quantity * entry_price`,
    dạng "K USD" khi ≥ 1000).
  - **Lãi/Lỗ ròng** — `pnl`, màu theo dấu (`BULL_COLOR`/`BEAR_COLOR`).
  - **Return %** — `pnl_percent`.
- [x] Tab lọc: **Tất cả** / **Mua (LONG)** / **Bán (SHORT)** / **Lệnh thắng**
  (`pnl > 0`) / **Lệnh thua** (`pnl < 0`) — lọc `list[Trade]` ở UI/Presenter,
  không query mới (`trade_log_filter.py`). Tab SHORT **luôn rỗng** cho tới
  [`BOT-050`](BOT-050_short_selling_support.md) (không ẩn, đúng quyết định).
- [x] Ô tìm kiếm theo mã lệnh (`#216` hoặc `216`) / ngày tháng — lọc
  client-side (`search_trade_log_rows`).
- [x] Nút **Export** (CSV) từ `list[Trade]` **đang lọc/tìm hiện tại** (không
  phải toàn bộ) — khớp với những gì user đang nhìn thấy trên bảng.
- [x] Phân trang — `trade_log_pagination.py`, `PAGE_SIZE = 20`.

### 2.2 Dòng mở rộng chi tiết — cần [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md) ✅

Bấm vào 1 lệnh → xổ ra 3 khối (theo mockup dòng `#216`):

- [x] **"Lý do vào lệnh (Entry Catalyst)"** — `Trade.entry_reason` (nguồn gốc
  là `Signal.reason`, vd *"QML Liquidity Sweep + EMA 21 Resistance"*).
- [x] **"Lý do thoát lệnh (Exit Execution)"** — `Trade.exit_reason` (vd *"Chạm
  Stop Loss (SL)"*). Map enum → nhãn tiếng Việt dễ đọc.
- [x] **"Chỉ số đánh giá & Thời lượng"** — render **động theo key** có trong
  `Trade.metadata` (**không hardcode** "QML Score" — user nêu rõ *"tùy vào
  chiến thuật"*), cộng thời lượng tính từ `exit_time - entry_time`, format
  "4h 00m".
- [x] UI phải chịu được `metadata` **rỗng hoặc có key lạ** mà không crash —
  đây là cái giá của thiết kế mở, đã chấp nhận có chủ đích ở `BOT-045`.

Làm xong trong [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md)
(action item cuối của file đó), không phải task riêng: mỗi dòng
`BackTestTradeLogs.qml` giờ là 1 `Button` (bấm mở/đóng — không phải
`Rectangle+MouseArea`, giữ đúng quy ước "click test được từ Python" đã đúc
kết ở §2.1) cộng 1 `Rectangle` chi tiết ẩn/hiện theo state `expandedRows`
trên root. Xem chi tiết implementation ở mục 6 của file `BOT-045`.

## 3. Rủi ro / Lưu ý

- 2.1 làm được độc lập; 2.2 bị chặn bởi `BOT-045`. Nếu `BOT-045` chưa xong,
  vẫn ship được 2.1 (bảng đầy đủ, chỉ chưa mở rộng được). **Đã ship theo
  đúng kịch bản này** — `BOT-045` ở backlog tại thời điểm 2.1 hoàn thành,
  rồi làm xong ngay sau đó, đóng nốt 2.2.
- Dữ liệu có thể lớn (mockup 44 lệnh, thực tế có thể hàng nghìn) — dùng model
  chuẩn của `QTableView`, không dựng list widget thủ công. **Đã làm**: panel
  này vốn đã là QML (từ `BOT-022`, hybrid layout với `ChartCard`), không phải
  QtWidgets — "model chuẩn, không hand-roll" áp dụng thành `ListView` được
  virtualize sẵn (chỉ render delegate cho hàng đang hiển thị) + phân trang
  20 lệnh/trang ở Presenter, không đẩy hết list vào QML property một lần.

## 4. Phụ thuộc

- [`BOT-022`](BOT-022_backtest_screen_static_ui.md) — khung màn hình.
- `BOT-021` ✅ — `Trade`/`BacktestResult`.
- [`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md) — **chặn** mục 2.2.
- [`BOT-050`](BOT-050_short_selling_support.md) — dữ liệu cho tab SHORT.
