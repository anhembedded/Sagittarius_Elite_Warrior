# PROP-004: Bộ Lọc Marker Nâng Cao Trên Biểu Đồ Backtest (Advanced Chart Marker Filter Controls)

- **ID**: `PROP-004`
- **Type**: Proposal / UX Enhancement
- **Module**: `Backtest Screen / BackTestTopPanel / MarkerLayer`
- **Status**: `Backlog`
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

Hiện tại, người dùng chỉ có một checkbox duy nhất: **"Hiển thị Marker lệnh"** (Bật/Tắt toàn bộ). Khi chạy backtest trên tập dữ liệu dài (ví dụ 1 năm) với chiến lược scalping hoặc lướt sóng tần suất cao (hàng trăm lệnh), việc bật tất cả marker khiến biểu đồ bị che lấp bởi mật độ marker quá dày đặc. Người dùng không có cách nào để:
- Chỉ quan sát các lệnh thua để tìm lỗi logic chiến lược.
- Chỉ quan sát các lệnh có lợi nhuận đột biến ($> 5\%$) để đánh giá điều kiện vào lệnh.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Thêm Menu Lọc Nhanh Marker trên Thanh Điều Khiển Chart**:
   - Bên cạnh nút toggle "Marker Lệnh", thêm dropdown / popover bộ lọc:
     - **Lọc theo Kết quả (Outcome)**:
       - *Tất cả lệnh (All)*
       - *Chỉ lệnh Thắng (Wins Only)*
       - *Chỉ lệnh Thua (Losses Only)*
     - **Lọc theo Vị thế (Side)**:
       - *Tất cả (All)*
       - *Chỉ lệnh Long (Long Only)*
       - *Chỉ lệnh Short (Short Only)*
     - **Lọc theo Ngưỡng PnL (Min $|PnL|$ Threshold)**:
       - Slider hoặc input số để chỉ hiện các lệnh có $|PnL| \ge X\%$.
2. **Cập nhật tức thì không cần chạy lại Backtest**:
   - Khi thay đổi bộ lọc trên UI, chỉ cần cập nhật danh sách marker đưa vào `MarkerLayer.set_markers()`, không cần re-run engine backtest.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng Clean Architecture
- **ViewModel (`backtest_view_model.py`)**:
  - Thêm các thuộc tính: `markerFilterOutcome` (ALL/WIN/LOSS), `markerFilterSide` (ALL/LONG/SHORT), `markerFilterMinPnl` (float).
- **Presenter (`backtest_presenter.py`)**:
  - Thêm phương thức `_apply_chart_marker_filters(result: BacktestResult)` để lọc danh sách `result.trades` trước khi gọi `trade_flag_markers()`.
  - Kết nối signal từ ViewModel để trigger update layer tức thì (< 5ms).
- **QML Component (`BackTestTopPanel.qml` / `MarkerFilterPopup.qml`)**:
  - Thiết kế popover gọn gàng theo chuẩn QML theme của ứng dụng.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1**: Chọn "Wins Only" chỉ hiển thị các cặp marker của các trade có $PnL > 0$.
- [ ] **AC-2**: Chọn "Losses Only" chỉ hiển thị các cặp marker của các trade có $PnL \le 0$.
- [ ] **AC-3**: Thay đổi bộ lọc phản hồi tức thì trên biểu đồ (< 16ms), không làm reset view range của người dùng.
- [ ] **AC-4**: Trạng thái bộ lọc được lưu giữ và khôi phục an toàn qua ViewModel.
- [ ] **AC-5**: Unit tests kiểm tra đầy đủ các kịch bản lọc marker.
