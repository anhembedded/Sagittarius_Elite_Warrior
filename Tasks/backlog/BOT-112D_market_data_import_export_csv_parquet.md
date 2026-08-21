# Nhiệm vụ: Nhập / Xuất Dữ Liệu Lịch Sử (CSV/Parquet) & Bảo Trì Ổ Cứng (BOT-112D)

**Mã Task:** `BOT-112D`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Thuộc Epic:** [`BOT-112`](BOT-112_data_management_and_market_vault_overhaul_epic.md) (Market Data Vault Overhaul)  
**Phụ thuộc:** [`BOT-112A`](../completed/BOT-112A_data_management_core_actions_and_timeframe_support.md)

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
