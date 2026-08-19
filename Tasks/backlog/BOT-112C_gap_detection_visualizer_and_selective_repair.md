# Nhiệm vụ: Trực Quan Hóa Lỗ Hổng & Vá Từng Đoạn Dữ Liệu (BOT-112C)

**Mã Task:** `BOT-112C`  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Thuộc Epic:** [`BOT-112`](BOT-112_data_management_and_market_vault_overhaul_epic.md) (Market Data Vault Overhaul)  
**Phụ thuộc:** [`BOT-112A`](BOT-112A_data_management_core_actions_and_timeframe_support.md)

---

## 1. Mục Tiêu

Thay thế nhãn `GAPS DETECTED` trừu tượng bằng thanh đo độ phủ dữ liệu trực quan (Data Coverage Timeline Bar) và cung cấp tính năng **Vá Lỗ Hổng Chọn Lọc (Selective Gap Repair)** tải đúng khoảng thời gian bị thiếu từ sàn Binance.

---

## 2. Các Hạng Mục Công Việc Chi Tiết

1. **Thanh Trực Quan Hóa Độ Phủ Dữ Liệu (Timeline Coverage Bar)**:
   - Hiển thị một thanh ngang biểu diễn trục thời gian của Symbol/Interval đã lưu:
     - 🟩 **Xanh lá**: Dữ liệu liên tục đầy đủ 100%.
     - 🟥 **Vạch đỏ**: Vùng bị mất dữ liệu (thủng nến).
2. **Chi Tiết Lỗ Hổng (Gap Inspector List)**:
   - Khi bấm vào dòng bị Gap, hiển thị danh sách chi tiết:
     - `Lỗ hổng #1`: từ `2024-05-01 10:00` đến `2024-05-01 18:00` (thiếu 480 nến).
     - `Lỗ hổng #2`: từ `2024-08-12 00:00` đến `2024-08-12 04:30` (thiếu 270 nến).
3. **Tính Năng Vá Lỗ Hổng (Fill Gap Action)**:
   - Thêm nút **"Vá Lỗ Hổng (Fill Gap)"** cho từng đoạn hoặc nút **"Vá Tất Cả (Fix All Gaps)"**.
   - Handler chỉ gọi Binance REST API tải đúng phạm vi `[from_time, to_time]` của lỗ hổng và chèn vào SQLite mà không cần quét lại toàn bộ lịch sử.

---

## 3. Tiêu Chí Nghiệm Thu

1. Nhận diện chính xác 100% các lỗ hổng thời gian dựa trên bước nhảy chu kỳ (cadence) của Timeframe.
2. Nút "Vá Lỗ Hổng" tải bổ sung dữ liệu thành công và chuyển trạng thái hàng sang `CONTINUOUS (OK)`.
