# Nhiệm vụ: Hoàn Thiện Tác Vụ Cốt Lõi & Hỗ Trợ Đa Khung Thời Gian (BOT-112A)

**Mã Task:** `BOT-112A`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🟢 **Hoàn thành (2026-08-20)**  
**Thuộc Epic:** [`BOT-112`](../backlog/BOT-112_data_management_and_market_vault_overhaul_epic.md) (Market Data Vault Overhaul)  
**Phụ thuộc:** `BOT-004` ✅, `BOT-030` ✅

---

## 1. Mục Tiêu

Loại bỏ các thành phần "hình thức / placeholder" trên màn hình Quản lý Dữ liệu, hỗ trợ đầy đủ các khung thời gian (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`), tự động quét nạp danh sách shards SQLite khi mở màn hình, và triển khai chức năng xóa dữ liệu thật (`Clear/Purge`).

---

## 2. Các Hạng Mục Công Việc Chi Tiết

### A. Giao diện (QML & Presentation)
- **Gỡ bỏ Placeholder**: Xóa bỏ các nút giả lập *"Seed 1,000 Records"*, *"Export JSON"*, *"Purge Vault"* không hoạt động trên Header.
- **Thêm Timeframe Selector**: Bổ sung dropdown chọn khung thời gian (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`) vào nhóm `SYNC CONTROLS` (thay vì gán cứng `1m`).
- **Tích hợp Symbol Picker**: Thêm nút mở `SymbolPickerModal` cạnh trường chọn Symbol để tìm kiếm nhanh trong 1.361+ cặp giao dịch Binance.
- **Hộp thoại Xác nhận Xóa (Confirmation Dialog)**: Thêm modal cảnh báo an toàn khi người dùng bấm *"Clear Local Data"* hoặc *"Purge All"*.

### B. Logic & Presenter (Python)
- **Tự động Auto-Discover Shards**: Khi `DataManagementPresenter` khởi tạo hoặc view hiển thị, tự động quét thư mục `database/` (`*.db`) và populate danh sách vào `DatabaseStatusTableModel` mà không bắt người dùng bấm *"Scan All"*.
- **Triển khai Xóa Dữ Liệu Thật**:
  - `Clear Local Data`: Xóa bảng klines của Symbol/Interval đã chọn hoặc giải phóng shard SQLite tương ứng.
  - `Purge All`: Xóa toàn bộ dữ liệu SQLite đã lưu trên máy khi có sự đồng ý của người dùng.
- **Dynamic Interval Sync**: `_run_single_sync` và `_run_scan_all` nhận `interval` động từ UI thay vì hardcode `"1m"`.

---

## 3. Tiêu Chí Nghiệm Thu (Acceptance Criteria)

1. Mở màn hình Database: Bảng danh sách hiển thị ngay các symbol/interval đã có dữ liệu trên đĩa.
2. Người dùng có thể chọn và đồng bộ dữ liệu cho bất kỳ timeframe nào (`1m`, `5m`, `15m`, `1h`, `1d`).
3. Bấm *"Clear Local Data"* xóa sạch dữ liệu của Symbol đã chọn và giải phóng dung lượng đĩa thực tế.
4. Header không còn bất kỳ nút placeholder nào báo *"Not implemented yet"*.
5. 100% Unit, Integration và Sanity tests đạt trạng thái xanh.
