# Epic: Tối ưu hóa Tham số Chiến lược Tự động (Strategy Parameter Optimization Epic)

**Mã Epic:** `BOT-108`  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Ưu tiên:** ⚡ **P4 — Tinh chỉnh & Tối ưu hóa Tham số (Optimization & Automation)**  
**Liên quan:** [`BOT-044`](../completed/BOT-044_strategy_parameter_schema_declaration.md), [`BOT-047`](../completed/BOT-047_backtest_strategy_params_dialog.md), [`BOT-021`](../completed/BOT-021_static_backtest_engine.md)

---

## 1. Mục tiêu Epic

Giải phóng người dùng khỏi việc phải thay đổi thủ công từng con số trong hộp thoại thông số rồi bấm chạy lại:
1. **Grid Search Đa luồng (Multi-Core Parameter Sweep)**: Quét hàng trăm/hàng nghìn tổ hợp tham số chiến lược (VD: EMA Fast $5 \rightarrow 30$, EMA Slow $30 \rightarrow 120$) bằng `ProcessPoolExecutor` chạy nền song song.
2. **Bảng Xếp hạng & Lọc Kết quả Tối ưu (Leaderboard & Multi-Criteria Ranking)**: Xếp hạng các bộ tham số theo Sharpe Ratio, Net PnL, Profit Factor, hoặc Calmar Ratio.
3. **Bản đồ nhiệt Tham số 2D (2D Parameter Heatmap)**: Trực quan hóa tương tác giữa 2 tham số chính dưới dạng lưới màu $\rightarrow$ Giúp người dùng chọn **Vùng bình nguyên ổn định (Robust Plateau)** tránh điểm nhọn overfit.

---

## 2. Danh sách Task thành phần

| Task ID | Tên Nhiệm vụ | Độ phức tạp | Mô tả tóm tắt |
| :--- | :--- | :---: | :--- |
| **`BOT-108A`** | **Multi-Core Parameter Grid Search Engine** | 🔴 `L` | Engine quét lưới song song đa tiến trình, tính toán ma trận tham số, chống lock GIL và hỗ trợ hủy tác vụ cooperative. |
| **`BOT-108B`** | **Optimization Leaderboard & 2D Parameter Heatmap UI** | 🟡 `M` | Giao diện bảng xếp hạng kết quả tối ưu và biểu đồ nhiệt 2D tương tác trực tiếp (click vào ô để nạp ngay bộ tham số vào chart). |
