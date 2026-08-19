# Nhiệm vụ: Bảng Tra Cứu Nến KLine Inspector & Kiểm Định Tính Toàn Vẹn (BOT-112B)

**Mã Task:** `BOT-112B`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Thuộc Epic:** [`BOT-112`](BOT-112_data_management_and_market_vault_overhaul_epic.md) (Market Data Vault Overhaul)  
**Phụ thuộc:** [`BOT-112A`](BOT-112A_data_management_core_actions_and_timeframe_support.md)

---

## 1. Mục Tiêu

Cung cấp tính năng tra cứu chi tiết dữ liệu nến thô (KLine Data Inspector) cho bất kỳ cặp tiền và khung thời gian nào đã lưu trong SQLite, đồng thời cung cấp công cụ kiểm định phát hiện nến lỗi (Data Integrity Audit).

---

## 2. Các Hạng Mục Công Việc Chi Tiết

1. **Bảng Tra Cứu Nến (KLine Inspector Table)**:
   - Cho phép bấm đúp vào 1 dòng trong bảng Database Status hoặc bấm nút *"Xem Dữ Liệu (Inspect)"*.
   - Mở cửa sổ hiển thị bảng nến phân trang (Pagination): `Thời gian (UTC / Giờ địa phương)`, `Open`, `High`, `Low`, `Close`, `Volume`, `Quote Volume`, `Số lệnh (Trades)`.
   - Có thanh nhảy nhanh đến ngày giờ cụ thể (`Jump to Timestamp`).
2. **Kiểm Định Dữ Liệu Nến (Data Integrity Audit)**:
   - Quét và phát hiện các bản ghi bất thường:
     - $High < Low$ hoặc $High < Open/Close$.
     - $Volume < 0$ hoặc giá trị $NaN / Inf$.
     - Trùng lặp Timestamp trong cùng một interval.
   - Báo cáo cảnh báo màu đỏ và đề xuất xóa/sửa các bản ghi bị lỗi.

---

## 3. Tiêu Chí Nghiệm Thu

1. Tra cứu và tải 500 nến gần nhất trong vòng < 50ms từ SQLite shard.
2. Hiển thị bảng số liệu rõ ràng, format màu xanh/đỏ cho nến tăng/giảm.
3. Chạy được kiểm định nến lỗi và thông báo trực quan trên UI.
