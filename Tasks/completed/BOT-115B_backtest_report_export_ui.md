# Nhiệm vụ: Xuất Báo cáo Backtest từ UI

**Mã Task:** `BOT-115B`  
**Thuộc Epic:** [`BOT-115`](../backlog/BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🟢 **S (Fast Agent)**  
**Trạng thái:** ✅ Done (2026-09-22)  
**Dependencies:** [`BOT-115A`](BOT-115A_backtest_report_schema_and_serializer.md) ✅

---

## 1. Triển Khai

Thêm nút **"Lưu báo cáo"** cạnh khu kết quả màn Backtest, chỉ bật khi đã có kết quả thật (`_last_result is not None`).

Đường đi đã có sẵn tiền lệ trong chính presenter này — `_on_trade_log_export_requested()` (xuất Trade Logs ra CSV) dùng `QFileDialog.getSaveFileName` với hằng số tiêu đề/tên file/bộ lọc riêng. Task này lặp lại đúng khuôn đó, đổi bộ lọc thành `Sagittarius Report (*.sagi-report.json *.sagi-report.json.gz)` và tên gợi ý sinh động theo nội dung, ví dụ `ETHUSDT_5m_ema_crossover_20260820_1432.sagi-report.json`.

Thư mục mặc định: `reports/` cạnh `database/` (cùng cách suy ra qua `ConfigKeys`, có fallback `os.getcwd()` giống `_DEFAULT_DB_DIR_NAME` trong `binance_bot_module.py`), tự tạo nếu chưa có. User vẫn đổi được sang chỗ khác qua dialog.

---

## 2. Chi Tiết Cần Đúng

- **Xuất kết quả thật đang hiển thị, không phải toolbar hiện tại.** Nếu `isConfigDirty` đang bật (user đã chỉnh toolbar nhưng chưa chạy lại), file phải ghi **config của lần chạy đã sinh ra kết quả đó**, không phải config đang gõ dở. Ghi nhầm chỗ này là làm hỏng đúng thứ epic sinh ra để bảo vệ. Presenter đã có sẵn snapshot đó cho dirty-tracking (`BOT-095B`) nên chỉ cần dùng đúng biến.
- Khác với CSV export (xuất đúng phần **đang lọc/đang nhìn** — quyết định có chủ đích ghi trong `trade_log_export.py`), report **luôn xuất toàn bộ trades**: đây là ảnh chụp một lần chạy, không phải ảnh chụp màn hình.
- Xuất xong log một dòng nêu đường dẫn + số lệnh + dung lượng file.

---

## 3. Kiểm Thử

- Chưa có kết quả → nút tắt, bấm không làm gì.
- Dialog trả về chuỗi rỗng (user bấm Cancel) → không ghi file.
- `isConfigDirty=True` → file ghi config của lần chạy cũ, **không** phải giá trị toolbar mới.
- File sinh ra nạp lại được bằng đúng `from_json` của `BOT-115A`.

## Implementation notes (2026-09-22)

- **`ui/logic/report_export.py` (mới)** — thuần hàm + một lần ghi file, tách khỏi `backtest_presenter.py` đúng khuôn
  `trade_log_export.py` đã có (I/O nằm ở `logic/`, Presenter chỉ quyết định *khi nào* gọi): `resolve_engine_version()`
  đọc version thật của gói `sagittarius-engine` đã cài qua `importlib.metadata.version()` (fallback `"unknown"` khi
  `PackageNotFoundError`, không bao giờ raise — provenance thiếu vẫn hơn "Lưu báo cáo" bị crash); `resolve_default_reports_dir()`
  suy `ConfigKeys.BACKTEST_REPORTS_DIR` → fallback `<cwd>/reports`, tự tạo nếu chưa có (cùng khuôn `config.get(...) or <cwd>/<name>`
  của `DATABASE_DIR`); `suggest_report_filename()` sinh tên theo đúng ví dụ trong task, làm sạch ký tự không an toàn
  cho filesystem; `build_backtest_report()` map `BacktestRunConfig`/`BacktestResult` sang `BacktestReport` (`BOT-115A`);
  `write_backtest_report()` gọi `dump_backtest_report()` với gzip tuỳ theo đuôi `.gz`.
- **`_data_window()`** ưu tiên `result.committed_bars` (Realtime, nến thật đã evaluate) khi có, rơi xuống
  `result.equity_curve` khi không (Static — đúng docstring "đọc thẳng từ storage" của mode đó), và trả `None`/`None`/`0`
  cho một lần chạy rỗng thay vì đoán. Mutation-verify: tắt nhánh `committed_bars` → đúng 1 test đỏ vì `last_kline_close`
  bị suy từ `equity_curve` sai, phục hồi lại xanh.
- **Presenter giữ đúng ảnh chụp lần chạy đã sinh kết quả (§2 mục 1)**: thêm `self._last_result: BacktestResult | None`,
  gán cùng dòng với `self._last_run_config` trong `_on_backtest_succeeded` — trước đây Presenter **không hề giữ lại**
  `BacktestResult` đầy đủ sau khi chạy xong (chỉ trích `_all_trades` và vài snapshot ViewModel), nên đây là khoảng trống
  thật phải lấp, không phải việc thừa. `_on_report_export_requested()` luôn đọc `_last_run_config`/`_last_result`, không
  bao giờ đọc giá trị toolbar hiện tại — nên `isConfigDirty=True` không ảnh hưởng file xuất ra (test riêng xác nhận).
  Report luôn xuất `result.trades` đầy đủ (không lọc) vì đến từ `_last_result` nguyên vẹn, không qua bất kỳ view đã lọc
  nào của Trade Logs.
- **Nút "Lưu báo cáo"** thêm vào `backtest_top_panel.py` cạnh nút "Expand", tắt mặc định, bật lại theo đúng cờ
  `has_cards` mà `_sync_metrics_header()` đã dùng cho header/banner cảnh báo — cờ đó đã đúng nghĩa "có `BacktestResult`
  thật để hiển thị" nên dùng lại thay vì thêm property ViewModel mới trùng lặp. **Không** thêm `setStyleSheet()` cho nút
  mới: `tests/unit/architecture/test_app_styling_only_shrinks.py` (ADR D21) ratchet số lần gọi styling-riêng xuống, chỉ
  giảm không được tăng — nút mới render theo theme nền tảng thay vì sao chép style (đã lỗi thời) của `_btn_expand_metrics`.
- **Wiring**: `BackTestViewModel.exportReportRequested` (Signal) + `requestExportReport()` (`@Slot()`, theo đúng khuôn
  mọi nút khác của màn này) → `signal_wiring.py` nối `presenter._on_report_export_requested`. `_ask_report_export_path()`
  giữ `QFileDialog` ở Presenter (cần `self.view` làm parent), đúng tiền lệ `_ask_trade_log_export_path`.
  `app_version` đọc qua `ConfigKeys.APP_VERSION`/`self.config.get(...)`, đúng tiền lệ `welcome_presenter.py`.
- **21 test mới**: 12 test thuần cho `report_export.py` (mọi hàm, kể cả 2 nhánh `_data_window`, gzip/không-gzip đọc lại
  đúng bằng `load_backtest_report` của `BOT-115A`), 4 test presenter (`_last_result is None` → không mở dialog; ghi
  file đúng, nạp lại được; dialog Cancel → không gọi `write_backtest_report`; `isConfigDirty=True` → file vẫn ghi
  đúng config của lần chạy cũ, không phải toolbar mới) + 1 test top-panel (nút tắt lúc chưa có card, bật đúng lúc có
  card, click phát đúng tín hiệu). `ruff`/`mypy` sạch trên toàn `src/` (642 file). Bộ test liên quan
  (`test_backtest_presenter.py`, `test_backtest_top_panel_layout.py`, `test_report_export.py`, `tests/unit/architecture`)
  624 pass.
- **Không làm trong task này** (chuyển cho `BOT-115C`/`BOT-115D` của Epic `BOT-115`): nạp lại report vào UI, state FSM
  riêng cho chế độ xem báo cáo đã nhập, so sánh 2 báo cáo cạnh nhau.
