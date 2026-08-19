# Nhiệm vụ: Phân tách Dữ liệu In-Sample vs Out-of-Sample (OOS Blind Testing)

**Mã Task:** `BOT-107A`  
**Thuộc Epic:** [`BOT-107`](BOT-107_strategy_robustness_and_monte_carlo_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-021`](../completed/BOT-021_static_backtest_engine.md), [`BOT-095B`](../completed/BOT-095B_backtest_fsm_dirty_tracking.md)

---

## 1. Mục tiêu

1. **Cấu hình Phân vùng**:
   - Cho phép người dùng chọn tỷ lệ chia In-Sample / Out-of-Sample (VD: `70% / 30%` hoặc chọn mốc ngày phân tách `split_date`).
2. **Thực thi Độc lập**:
   - Chạy Pass 1 trên tập In-Sample (sinh ra `in_sample_metrics`).
   - Chạy Pass 2 trên tập Out-of-Sample với cùng bộ tham số mà không có sự thiên lệch (sinh ra `out_of_sample_metrics`).
3. **Hiển thị Đối sánh (Side-by-Side Comparison)**:
   - Trên Chart: Vẽ một đường đứt nét phân cách dọc giữa 2 vùng.
   - Trên Bảng Chỉ số: Hiển thị 2 cột số liệu song song: **In-Sample** vs **Out-of-Sample** (cảnh báo đỏ nếu hiệu suất OOS sụt giảm quá 40% so với In-Sample $\rightarrow$ dấu hiệu overfit rõ rệt).
