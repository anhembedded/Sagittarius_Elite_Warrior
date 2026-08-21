# Nhiệm vụ: Hỗ Trợ Đồng Bộ & Lưu Trữ Nến 1 Giây 1s (BOT-112E)

**Mã Task:** `BOT-112E`  
**Độ phức tạp:** 🟢 **S (Fast Agent)**  
**Trạng thái:** 🟢 **Hoàn thành (2026-08-20)**  
**Thuộc Epic:** [`BOT-112`](../backlog/BOT-112_data_management_and_market_vault_overhaul_epic.md) (Market Data Vault Overhaul)  
**Phụ thuộc:** [`BOT-112A`](BOT-112A_data_management_core_actions_and_timeframe_support.md), [`BOT-112B`](BOT-112B_kline_data_inspector_and_integrity_audit.md)

---

## 1. Mục Tiêu

Bổ sung hỗ trợ toàn diện cho khung thời gian 1 giây (`1s` - Sub-minute / High-frequency KLines) trên màn hình Quản Lý Dữ Liệu Thị Trường (Market Data Hub / Storage Vault), cho phép người dùng lựa chọn, đồng bộ từ Binance REST API, kiểm tra dữ liệu và lưu trữ vào SQLite shards.

---

## 2. Các Hạng Mục Công Việc Chi Tiết

1. **Khung Thời Gian Domain & ViewModel**:
   - `TimeFrame.ONE_SECOND = "1s"` (1 giây) đã được khai báo chuẩn trong Domain Value Object (`src/domain/value_objects/timeframe.py`).
   - Cập nhật `_SUPPORTED_INTERVALS` trong `DataManagementViewModel` để tự động lấy đầy đủ tất cả các khung thời gian từ `TimeFrame` (`["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]`).
2. **Giao Diện UI (QML)**:
   - Dropdown `Timeframe` trên thanh `SYNC CONTROLS` của `DatabaseScreen.qml` hiển thị tùy chọn `1s`.
   - Bảng tra cứu `KLineInspectorModal.qml` và `GapInspectorModal.qml` hỗ trợ tải và hiển thị nến `1s`.
3. **Đồng Bộ Binance API & Shard Storage**:
   - `PythonBinanceClient` truyền trực tiếp `interval="1s"` tới endpoint `/api/v3/klines`.
   - `SqliteMarketDataRepository` lưu trữ bảng nến `klines_1s` trong shard tương ứng.
4. **Kiểm Thử (Unit Tests)**:
   - Kiểm thử `intervals` trong `DataManagementViewModel` chứa `"1s"`.
   - Kiểm thử `TimeFrame("1s").to_seconds() == 1`.

---

## 3. Tiêu Chí Nghiệm Thu (Acceptance Criteria)

1. Dropdown chọn Timeframe trên màn hình Database hiển thị tùy chọn `1s`.
2. Có thể chọn `1s` để chạy Scan, Sync dữ liệu từ Binance và xem dữ liệu trong KLine Inspector.
3. 100% test suite đạt kết quả xanh.
