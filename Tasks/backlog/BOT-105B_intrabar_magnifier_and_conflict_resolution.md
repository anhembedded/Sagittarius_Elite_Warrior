# Nhiệm vụ: Intra-bar Bar Magnifier & Giải quyết Xung đột SL/TP trên cùng 1 nến

**Mã Task:** `BOT-105B`  
**Thuộc Epic:** [`BOT-105`](BOT-105_advanced_order_execution_and_risk_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md), [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md)

---

## 1. Vấn đề: Nghịch lý Râu nến (Intra-bar Ambiguity)

Trong kiểm thử tĩnh (Static Backtest theo nến 5m/1h/1d):
Khi một cây nến có biên độ dao động lớn (`High` vượt qua mức `Take Profit` và `Low` đâm thủng mức `Stop Loss`):
- Nếu giả định nến chạm **TP trước** $\rightarrow$ Ghi nhận LÃI LỚN.
- Nếu giả định nến chạm **SL trước** $\rightarrow$ Ghi nhận LỖ.
- Các backtester thông thường thường chọn ngây thơ hoặc luôn lạc quan (giả định chạm TP trước) $\rightarrow$ Dẫn tới **ảo tưởng lợi nhuận (Backtest Over-optimism Bias)**.

---

## 2. Giải pháp (Bar Magnifier Engine)

Tận dụng hạ tầng Dữ liệu Tick 1s đã xây dựng từ [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md):
1. **Chế độ Static thông thường (Không có dữ liệu tick)**:
   - Áp dụng nguyên tắc phòng thủ thận trọng (Pessimistic Rule): Nếu nến chạm cả SL và TP $\rightarrow$ Luôn ưu tiên xử lý **Cắt lỗ (SL) trước**.
2. **Chế độ Nâng cao (Bar Magnifier / Phóng to thanh nến)**:
   - Khi phát hiện nến khung lớn (VD: 15m) chạm cả SL và TP, Engine tự động trích xuất chuỗi nến con 1s / 1m bên trong thanh nến đó để tái hiện quỹ đạo giá thực tế.
   - Xác định chính xác theo thời gian thực (Timestamp) xem giá chạm mốc nào trước trong lịch sử.

---

## 3. Tiêu chí Nghiệm thu

- Có test kiểm thử chứng minh: Ca nến quét 2 đầu ở chế độ thường luôn bảo thủ (cắt lỗ trước); ở chế độ Bar Magnifier xác định chuẩn xác theo chuỗi tick 1s.
- 0 lỗi tài chính, không rò rỉ dữ liệu tương lai (No Look-ahead bias).
