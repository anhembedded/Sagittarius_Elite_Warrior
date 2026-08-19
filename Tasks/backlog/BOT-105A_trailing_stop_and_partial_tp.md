# Nhiệm vụ: Trailing Stop, Break-Even Stop & Chốt lời từng phần (Partial TP)

**Mã Task:** `BOT-105A`  
**Thuộc Epic:** [`BOT-105`](BOT-105_advanced_order_execution_and_risk_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md), [`BOT-021`](../completed/BOT-021_static_backtest_engine.md)

---

## 1. Mục tiêu

Bổ sung 3 cơ chế quản trị lệnh động cốt lõi vào `PaperExchange`:
1. **Break-Even Stop**: Khi giá tăng đạt ngưỡng kích hoạt (VD: $+1R$ hoặc $+2\%$ lợi nhuận), hệ thống tự động dời `stop_loss_price` về mức giá vào lệnh (`entry_price` hoặc `entry_price + fee`) để bảo toàn vốn 100%.
2. **Trailing Stop**: 
   - Tham số: `trailing_activation_price` (ngưỡng bắt đầu bám) và `trailing_offset` (khoảng cách bám theo giá đỉnh).
   - Khi giá tạo đỉnh mới $H_{new}$, mức cắt lỗ mới = $H_{new} - \text{trailing\_offset}$. Nếu giá hồi về chạm mức này $\rightarrow$ Khớp lệnh thoát vị thế.
3. **Chốt lời từng phần (Partial Take Profit / Scaling Out)**:
   - Cho phép cấu hình danh sách mốc chốt lời: `[(price_1, 50%), (price_2, 50%)]`.
   - Khi giá chạm `price_1`, `PaperExchange` ghi nhận 1 phần lợi nhuận, giảm số lượng vị thế `quantity`, sinh ra 1 partial `Trade` log, và giữ 50% khối lượng còn lại tiếp tục gồng lãi.

---

## 2. Kiểm thử & Tiêu chí Nghiệm thu

- **Financial Invariants**:
  - Khi đóng 1 phần vị thế, tổng `quantity` đã đóng + còn lại luôn bằng `initial_quantity`.
  - Tổng số tiền thực nhận sau các lần partial exit khớp chính xác với số dư tài khoản.
  - Trailing stop không bao giờ dời lùi xuống theo hướng bất lợi (chỉ được dời lên theo chiều tăng lãi).
- **Unit Tests**:
  - Kiểm thử Break-even stop kích hoạt đúng thời điểm.
  - Kiểm thử Trailing stop bảo vệ lợi nhuận khi thị trường đảo chiều từ đỉnh.
  - Kiểm thử Scaling out với 2 mốc TP1 và TP2.
