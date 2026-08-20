# Nhiệm vụ: So sánh 2 Báo cáo Cạnh nhau

**Mã Task:** `BOT-115D`  
**Thuộc Epic:** [`BOT-115`](BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-115C`](BOT-115C_backtest_report_import_and_readonly_state.md)

---

## 1. Vì Sao Task Này Mới Là Đích Đến

3 task trước làm cho báo cáo *lưu được* và *mở lại được*. Nhưng lý do thật sự trader lưu báo cáo là để **đối chiếu**: "đổi EMA 200 sang 150 thì tốt lên hay xấu đi?", "thêm phí 0.075% thì chiến lược còn lãi không?", "bản engine mới có làm đổi kết quả chiến lược cũ không?".

Không có màn so sánh thì user phải mở 2 file lần lượt và tự ghi số ra giấy — đúng cái nỗi đau epic này sinh ra để xoá.

---

## 2. Triển Khai

Modal so sánh 2 cột (tái dùng `OverlayHost` của [`BOT-087`](../completed/BOT-087_overlay_host_engine.md), như mọi popup màn Backtest sau [`BOT-088`](../completed/BOT-088_migrate_backtest_popups_to_overlay_host.md)):

1. **Bảng diff cấu hình** — chỉ liệt kê field **khác nhau**, tái dùng thẳng `BacktestRunConfig.compute_diff_summary()` đã có sẵn (đang dùng cho banner dirty-tracking) thay vì viết logic so sánh thứ hai.
2. **Bảng metrics side-by-side** — mọi chỉ số của `BacktestMetrics` xếp 2 cột + cột chênh lệch, tô xanh/đỏ theo hướng tốt/xấu. Cẩn thận: với `max_drawdown_percent` hay `max_consecutive_losses` thì **nhỏ hơn là tốt hơn** — không được tô màu máy móc theo dấu của hiệu số.
3. **Equity curve chồng lên nhau** — 2 đường trên cùng một trục, chuẩn hoá về cùng mốc 100% nếu `initial_balance` khác nhau (không chuẩn hoá thì so 2 lần chạy khác vốn là vô nghĩa).
4. Nguồn của mỗi cột: một file trên đĩa, hoặc kết quả đang hiển thị trên màn hình.

---

## 3. Kiểm Thử

- 2 report cùng config, khác kết quả → bảng diff config rỗng, có thông báo *"Cấu hình giống hệt nhau"* thay vì bảng trống khó hiểu.
- Chỉ số "nhỏ hơn là tốt hơn" tô màu đúng chiều.
- 2 report khác `initial_balance` → đường vốn chuẩn hoá đúng.
- 2 report khác symbol/timeframe → vẫn so được nhưng có cảnh báo rõ đây là so sánh giữa 2 thị trường khác nhau.
