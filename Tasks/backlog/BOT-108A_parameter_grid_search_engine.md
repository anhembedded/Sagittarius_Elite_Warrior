# Nhiệm vụ: Multi-Core Parameter Grid Search Engine

**Mã Task:** `BOT-108A`  
**Thuộc Epic:** [`BOT-108`](BOT-108_strategy_parameter_optimization_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-021`](../completed/BOT-021_static_backtest_engine.md), [`BOT-044`](../completed/BOT-044_strategy_parameter_schema_declaration.md), [`BOT-095C`](../completed/BOT-095C_backtest_cancellation_and_stop_button.md)

---

## 1. Mục tiêu

Xây dựng Engine quét tham số song song hiệu năng cao:
1. **Parameter Grid Generator**:
   - Dựa trên `ParameterSchema` của chiến lược, sinh ra tích Descartes (Cartesian product) của tất cả các dải giá trị `[start, stop, step]`.
2. **Parallel Worker Pool (`ProcessPoolExecutor`)**:
   - Phân chia $K$ tổ hợp tham số thành các batch nhỏ cho các CPU worker chạy song song độc lập.
   - Tránh hoàn toàn GIL contention (không làm đơ UI thread).
3. **Cooperative Cancellation & Progress Reporting**:
   - Báo cáo tiến độ: `X / Total combinations (Y% - ETA: Zs)`.
   - Cho phép người dùng bấm nút Dừng / Hủy bất cứ lúc nào.
