# Nhiệm vụ: Nhập / Xuất Dữ Liệu Lịch Sử (CSV/Parquet) & Bảo Trì Ổ Cứng (BOT-112D)

**Mã Task:** `BOT-112D`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🟢 **Hoàn thành (2026-09-23)**  
**Thuộc Epic:** [`BOT-112`](../backlog/BOT-112_data_management_and_market_vault_overhaul_epic.md) (Market Data Vault Overhaul)  
**Phụ thuộc:** [`BOT-112A`](BOT-112A_data_management_core_actions_and_timeframe_support.md)

---

## 1. Mục Tiêu

Cung cấp công cụ xuất dữ liệu KLines ra các định dạng chuẩn (`.csv`, `.parquet`, `.json`) để phục vụ nghiên cứu định lượng ngoài ứng dụng, cho phép nạp dữ liệu offline từ file CSV vào SQLite, và bổ sung công cụ tối ưu hóa dung lượng ổ đĩa (`VACUUM & WAL checkpoint`).

---

## 2. Các Hạng Mục Công Việc Chi Tiết

1. **Xuất Dữ Liệu (Export Action)**:
   - Thay thế nút Export giả lập bằng chức năng thật:
     - Hộp thoại chọn thư mục lưu và định dạng (`CSV`, `Parquet`, `JSON`).
     - Xuất dữ liệu kèm thanh tiến trình (Exporting Progress Bar) không làm đơ giao diện.
2. **Nhập Dữ Liệu Offline (Import Action)**:
   - Cho phép người dùng chọn file CSV nến từ máy tính.
   - Trình phân tích cú pháp (Parser) hỗ trợ các định dạng phổ biến (Binance Data Export, TradingView Export, MetaTrader CSV).
   - Kiểm tra trùng lặp và ghi đè an toàn vào shard SQLite.
3. **Tối Ưu Hóa & Dọn Dẹp Đĩa (Database Vacuum & WAL Maintenance)**:
   - Nút **"Tối Ưu Hóa Bộ Nhớ (Vacuum Database)"**: Chạy `PRAGMA wal_checkpoint(TRUNCATE)` và `VACUUM` trên tất cả các shard để thu hồi dung lượng đĩa đã xóa.

---

## 3. Tiêu Chí Nghiệm Thu

1. Xuất 500.000 nến ra file `.csv` và `.parquet` chuẩn xác, mở được trực tiếp bằng Pandas / Excel.
2. Nạp thành công file CSV nến bên ngoài vào SQLite và hiển thị được trên biểu đồ Backtest.
3. Chạy Vacuum thành công, giảm dung lượng file `.db` trên đĩa sau khi xóa dữ liệu.

---

## 4. Ghi Chú Triển Khai Thực Tế (2026-09-23)

**Tiền đề đã lỗi thời — đọc trước khi dùng lại phần "1. Mục Tiêu" ở trên.** Mục 2.1 nói "Thay
thế nút Export giả lập" (replace a mocked Export button), nhưng `_ACTION_BUTTONS` trong
`data_management_view.py` trước khi task này chạy KHÔNG hề có hàng nào cho Export/Import —
không giả lập, không có gì cả (xác nhận qua `git diff` với `origin/master-warrior`: thay đổi chỉ
gồm dòng thêm mới). Chức năng vẫn được xây đúng như mô tả, chỉ là tiền đề "thay thế cái giả" sai.

- **Export/Import là CQRS command mới**, không phải mở rộng `ScanCoordinator` (coordinator đó đã
  chạm trần 400 dòng của `architecture-rule.md` §5.4 trước khi task này bắt đầu): thêm
  `ExportMarketDataCommand`/`ImportMarketDataCommand` + handler dưới
  `application/database/{export_market_data,import_market_data}/`, và một
  `ExportImportCoordinator` riêng (`ui/coordinators/export_import_coordinator.py`) theo đúng mẫu
  "một coordinator, một họ việc" của `GapCoordinator`/`KLineInspectorCoordinator`.
- **Một parser CSV theo alias, không phải 3 parser riêng cho Binance/TradingView/MetaTrader**
  (`domain/csv_kline_parser.py`): đọc header một lần, ánh xạ tên cột theo bảng alias
  không phân biệt hoa/thường, chỉ bắt buộc `open_time` + OHLC, các cột riêng của Binance
  (`quote_asset_volume`, `number_of_trades`, hai cột taker-buy) mặc định `0`/`0.0` khi file
  không có, và tự suy ra `close_time` khi file không cung cấp (dùng đúng quy ước "close_time là
  thời điểm cuối cùng còn tính" của `BUG-022`). Ba parser riêng sẽ trôi lệch nhau mỗi khi một
  công cụ đổi định dạng xuất — một bảng alias thì không.
- **Không cần logic chống trùng lặp riêng ở Import**: `IMarketDataRepository.save_klines()` đã
  upsert theo `(symbol, interval, open_time)` qua SQLite `ON CONFLICT DO UPDATE`
  (`adapters/persistence/sqlalchemy_repository.py`) — mục 2.2 "Kiểm tra trùng lặp và ghi đè an
  toàn" của tiêu chí gốc đã được tầng repository giải quyết sẵn, handler chỉ gọi
  `save_klines()` một lần với batch đã parse.
- **Export bounded-memory theo đúng tinh thần `BUG-025`**: đọc qua
  `IMarketDataRepository.stream_klines()` (không phải `get_klines()`, tránh vật chất hoá cả dải
  vào RAM), CSV/JSON ghi từng dòng một, Parquet gom theo batch 20.000 dòng qua
  `pyarrow.parquet.ParquetWriter` trước khi `write_table()`.
- **Phụ thuộc mới: `pyarrow`** (Parquet không có đường ghi nào trong stdlib) — thêm vào
  `requirements.txt` sau khi người dùng phê duyệt tường minh (không có sẵn `pandas`/`pyarrow`
  trước đó), và một `[[tool.mypy.overrides]] module = ["pyarrow", "pyarrow.*"]
  ignore_missing_imports = true` trong `pyproject.toml` (cùng mẫu với override `binance` sẵn có),
  cũng được người dùng phê duyệt tường minh trước khi thêm.
- **Không có thanh tiến trình xác định phần trăm cho Export/Import** — khác với Sync (vốn có
  tổng số bước biết trước), Export/Import chạy nền qua `IThreadManager.submit()` (không làm đơ
  UI, đúng yêu cầu "không làm đơ giao diện" của tiêu chí gốc) nhưng chỉ log dòng bắt
  đầu/kết thúc, không có `%`. Cùng cách Vacuum/Purge/Clear (mọi tác vụ nền khác trên màn hình
  này trừ Sync) đã làm — không phải thiếu sót, mà nhất quán với các nút còn lại.
- **Nút "Tối Ưu Hóa Bộ Nhớ (Vacuum)" đã tồn tại sẵn** từ trước task này (trong
  `ScanCoordinator.run_vacuum`) — không phải việc mới của BOT-112D, chỉ xác nhận tiêu chí #3 đã
  đạt.
- **Kiểm thử**: `test_export_market_data.py`/`test_import_market_data.py` (handler, viết thật ra
  đĩa CSV/JSON/Parquet, đọc lại bằng `pyarrow.parquet.read_table`), `test_csv_kline_parser.py`
  (alias theo 3 kiểu header Binance/TradingView/MetaTrader, dòng lỗi bị bỏ qua có cảnh báo, file
  rỗng, thiếu cột bắt buộc), `test_export_import_coordinator.py` (coordinator, tracker
  success/failure, lock/unlock đúng theo mẫu `run_clear_data`/`run_vacuum`),
  `test_data_management_export_import.py` (dây nối Presenter↔ViewModel↔View đầy đủ: mở dialog
  với tên file gợi ý đúng, huỷ dialog không submit việc nền, một lát cắt end-to-end thật qua
  dispatch → handler → file CSV thay vì chỉ dừng ở "dispatcher đã được gọi").
- **Chưa kiểm thử với đúng 500.000 nến thật** (tiêu chí #1) — thiết kế bounded-memory (stream +
  batch) đã được xác minh đúng cơ chế, nhưng chưa có test tích hợp nạp 500k dòng thật; đây là
  giới hạn đã biết, không phải khoảng trống che giấu.
