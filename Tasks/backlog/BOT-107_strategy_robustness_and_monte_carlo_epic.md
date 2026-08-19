# Epic: Kiểm định Độ tin cậy Chiến lược & Mô phỏng Monte Carlo (Strategy Robustness & Monte Carlo Epic)

**Mã Epic:** `BOT-107`  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Ưu tiên:** 🛡️ **P3 — Kiểm định Chống Overfitting & Đánh giá Rủi ro Phá sản (Anti-Overfitting & Ruin Risk)**  
**Liên quan:** [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md), [`BOT-021`](../completed/BOT-021_static_backtest_engine.md), [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md)

---

## 1. Mục tiêu Epic

Bảo vệ người dùng khỏi bẫy **"Tối ưu quá mức / Học vẹt dữ liệu quá khứ" (Curve-fitting / Overfitting Bias)**:
1. **Kiểm định Mù Out-of-Sample (OOS Validation)**: Tách dữ liệu thành 2 phân vùng độc lập (In-Sample để tinh chỉnh tham số, Out-of-Sample hoàn toàn cô lập để thẩm định hiệu suất thực tế).
2. **Mô phỏng Ngẫu nhiên Monte Carlo (Monte Carlo Simulation)**:
   - Xáo trộn ngẫu nhiên thứ tự các lệnh đã khớp 5,000 - 10,000 lần (Trade Reshuffling).
   - Mô phỏng biến động trượt giá & sai số vào lệnh (Noise Injection).
   - Xuất ra xác suất cháy tài khoản (Risk of Ruin %) và khoảng tin cậy 95% (p95 Max Drawdown).

---

## 2. Danh sách Task thành phần

| Task ID | Tên Nhiệm vụ | Độ phức tạp | Mô tả tóm tắt |
| :--- | :--- | :---: | :--- |
| **`BOT-107A`** | **Phân tách Dữ liệu In-Sample vs Out-of-Sample (OOS)** | 🔴 `L` | Hỗ trợ chọn tỷ lệ chia (VD: 70% In-Sample / 30% Out-of-Sample); hiển thị đường phân cách và so sánh 2 bảng chỉ số riêng biệt. |
| **`BOT-107B`** | **Mô phỏng Monte Carlo & Đánh giá Nguy cơ Phá sản (Risk of Ruin)** | 🔴 `L` | Chạy 10,000 kịch bản ngẫu nhiên xáo trộn chuỗi trade, vẽ chùm đường Equity Curve (Spaghetti Chart) và tính xác suất sụt giảm vốn. |
