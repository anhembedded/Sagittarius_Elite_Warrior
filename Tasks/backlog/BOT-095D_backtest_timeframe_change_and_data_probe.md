# Nhiệm vụ: BOT-095D — 1-Click Auto-Sync & Run, Date Range Gap Check & Live Chart Preview

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: [`BOT-095B`](BOT-095B_backtest_fsm_and_stale_data_lifecycle.md).
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
   - So khớp với khoảng thời gian yêu cầu `[req_start_time, req_end_time]`:
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
2. Presenter khởi chạy `BulkSyncMarketDataCommand` (hoặc `SyncMarketDataCommand`) với symbol và timeframe được chọn.
3. **Kế thừa Progress Bar:** Lắng nghe tiến độ đồng bộ (`SyncProgressEvent`) từ EventBus hoặc Handler (đã có sẵn trong Data Management) để cập nhật % tải dữ liệu mượt mà lên Toolbar:
   > *"Đang đồng bộ nến {timeframe} từ Binance: 45% (1,200 / 2,600 nến)..."*
4. **Tự động chuyển tiếp:** Khi sync thành công $\rightarrow$ Dispatch `SYNC_SUCCEEDED` $\rightarrow$ FSM tự động chuyển sang `BacktestUiState.RUNNING` và chạy ngay `RunStaticBacktestCommand` mà **không yêu cầu người dùng phải bấm nút lần thứ hai**.

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
   - Phát hiện đúng các khoảng trống dữ liệu ngày bắt đầu / ngày kết thúc.
3. **Preview nến tức thì**:
   - Đổi khung `1m` sang `5m` có data $\rightarrow$ Chart cập nhật nến `5m` ngay lập tức.
4. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.
