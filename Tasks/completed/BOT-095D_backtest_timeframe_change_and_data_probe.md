# Nhiệm vụ: BOT-095D — 1-Click Auto-Sync & Run, Date Range Gap Check & Live Chart Preview

> Trạng thái: ✅ Hoàn thành 2026-08-17

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: `BOT-095B` ✅, [`BOT-095H`](BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md), sau `BOT-095C`.
> **Trọng tâm**: Xử lý vòng đời chuyển đổi Timeframe, tự động kiểm tra độ bao phủ nến (Date Range Gap Check) trong SQLite, nạp nến xem trước (Preview) lên biểu đồ, và xây dựng cơ chế **1-Click Auto-Sync & Run** (tự động đồng bộ với Progress Bar kế thừa từ Data Management rồi chạy tiếp Backtest chỉ với 1 click).

---

## 1. Vấn đề Hiện tại

1. **Trải nghiệm rời rạc khi thiếu dữ liệu:**
   - Khi chọn một timeframe hoặc khoảng thời gian chưa có đủ nến trong DB: người dùng bấm Chạy $\rightarrow$ Bị báo lỗi $\rightarrow$ Bấm nút "Đồng bộ ngay" $\rightarrow$ Chờ tải $\rightarrow$ Bấm lại nút "Chạy Backtest" (3 bước thủ công).
2. **Kiểm tra sơ sài chỉ đọc `limit=1`:**
   - Nếu chỉ kiểm tra có ít nhất 1 nến thì sẽ bỏ sót trường hợp DB chỉ có nến của 1 tháng trong khi người dùng yêu cầu 6 tháng.
3. **Chart không cập nhật nến xem trước khi đổi Timeframe.**

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Date Range Gap Check & Fast Data Probe
Khi nhận signal `selectedTimeframeChanged` hoặc `timeRangeChanged`:
1. **Kiểm tra độ bao phủ dữ liệu trong SQLite (Range Coverage Probe):**
   - Query kiểm tra biên trong SQLite:
     - `db_min_time` = nến sớm nhất trong DB của symbol + timeframe đó.
     - `db_max_time` = nến muộn nhất trong DB.
     - `candle_count` = tổng số nến hiện có.
   - Chuẩn hóa timezone UTC và dùng khoảng half-open `[req_start_time, req_end_time)`. Min/max chỉ là fast precheck; sau đó phải kiểm các timestamp kỳ vọng theo cadence của timeframe để phát hiện **gap nội bộ**, duplicate và nến cuối chưa đóng:
     ```python
     is_fully_covered = (db_min_time is not None) and (db_min_time <= req_start_time) and (db_max_time >= req_end_time)
     ```
2. **Nếu dữ liệu bao phủ đầy đủ (`is_fully_covered == True`):**
   - Tải tập nến gần nhất lên `ChartCard` để hiển thị khung thời gian mới ở chế độ xem trước (Preview).
   - Tắt cờ `needsDataSync = False`.
3. **Nếu dữ liệu bị thiếu hoặc chưa có (`is_fully_covered == False`):**
   - Bật cờ `needsDataSync = True` trên `BackTestViewModel`.
   - Hiển thị badge cảnh báo: *"Dữ liệu trong máy ({db_min_time} - {db_max_time}) chưa đủ khoảng đã chọn."*

### 2.2. Cơ chế 1-Click Auto-Sync & Run (Kế thừa Progress Bar từ Data Management)
Khi người dùng bấm "Chạy Backtest" mà `needsDataSync == True`:
1. FSM tự động chuyển sang `BacktestUiState.SYNCING`.
2. Presenter khởi chạy command sync với **config snapshot/action_id đã tạo**, không đọc toolbar ở callback.
3. **Kế thừa Progress Bar:** Lắng nghe tiến độ đồng bộ (`SyncProgressEvent`) từ EventBus hoặc Handler (đã có sẵn trong Data Management) để cập nhật % tải dữ liệu mượt mà lên Toolbar:
   > *"Đang đồng bộ nến {timeframe} từ Binance: 45% (1,200 / 2,600 nến)..."*
4. **Tự động chuyển tiếp:** Khi sync thành công, re-probe đúng range/cadence rồi chỉ dispatch `SYNC_SUCCEEDED` và chạy tiếp nếu action_id vẫn active. Thiếu gap sau sync phải báo chính xác segment còn thiếu, không chạy backtest trên dữ liệu một phần.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- ✏️ `src/presentation/ui/screens/backtest/backtest_presenter.py`: Cài đặt Date Range Gap Check và chuỗi Auto-Sync & Run liên hoàn.
- ✏️ `src/presentation/ui/screens/backtest/backtest_view_model.py`: Thêm các property `syncProgressPercent`, `syncProgressText`, `isDataFullyCovered`.
- ✏️ `src/presentation/ui/screens/backtest/BackTestTopPanel.qml`: Hiển thị thanh Sync Progress Bar kế thừa phong cách từ Data Management.
- ✏️ `tests/unit/presentation/ui/screens/test_backtest_presenter.py`: Bổ sung test cases:
  - Chọn timeframe thiếu data $\rightarrow$ Bấm Run $\rightarrow$ Tự động SYNCING $\rightarrow$ Tự động RUNNING $\rightarrow$ COMPLETED.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **1-Click Hoàn tất**:
   - Thiếu dữ liệu nến $\rightarrow$ Người dùng bấm "Chạy Backtest" đúng 1 lần $\rightarrow$ Hệ thống tự động tải nến kèm progress bar rồi tính toán ra kết quả.
2. **Gap Check chính xác**:
   - Phát hiện gap đầu/cuối **và gap nội bộ**, boundary UTC và nến chưa đóng.
3. **Preview nến tức thì**:
   - Đổi khung `1m` sang `5m` có data $\rightarrow$ Chart cập nhật nến `5m` ngay lập tức.
4. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -Full` đạt 100% Passed.

5. **Race verification**:
   - `sync-success-after-invalidated-config` không auto-run và không ghi đè preview/UI hiện tại.

---

## 5. Kết quả triển khai

- Đổi timeframe/range tạo preview background có generation ID; callback cũ
  không được ghi đè chart hiện tại.
- Run kiểm coverage bằng fast SQLite aggregate. Thiếu data tự chuyển sang
  sync, hiển thị progress, re-probe rồi mới chạy tiếp; không sync loop.
- ViewModel/QML hiển thị coverage warning và sync progress.
- “Toàn bộ lịch sử” chỉ cam kết liên tục từ nến local sớm nhất đến nến đóng
  gần nhất; không giả vờ biết mốc lịch sử đầu tiên của Binance.

## 6. Regression 2026-08-17 — Retry sau re-probe lỗi

- Sửa contract lệch: nút “Đồng bộ dữ liệu ngay” hiện/enabled trong `ERROR`
  nhưng FSM từng từ chối `SYNC_REQUESTED`, khiến click không có tác dụng.
- Freeze mốc cuối của “Toàn bộ lịch sử” trước background work và fetch dư
  đúng một interval để thích ứng end-boundary exclusive của Binance; re-probe
  vẫn dùng khoảng half-open ban đầu, không chạy theo một mốc `now` di động.
- Loại bỏ `implicitHeight` binding loop và defer resize QQuickWidget sang event
  loop kế tiếp để tránh chuỗi cảnh báo `QQuickRenderControl` khi banner đổi.
- Regression giữ lại thao tác QML từ `ERROR`, boundary sync và Qt warning gate.
