# PROP-003: Chi Tiết Marker Thích Ứng Mức Phóng To (Zoom-Adaptive Trade Marker PnL Details)

- **ID**: `PROP-003`
- **Type**: Proposal / UX Enhancement
- **Module**: `ChartCard / MarkerLayer / MarkerLOD`
- **Status**: `Backlog`
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

- Khi biểu đồ ở mức zoom xa (toàn bộ lịch sử hàng nghìn cây nến), việc ẩn text và chỉ vẽ icon tam giác nhỏ gọn là thiết kế tối ưu để tránh rối mắt và bảo toàn FPS.
- Tuy nhiên, khi người dùng zoom sâu vào một đoạn ngắn (chỉ có từ 10 đến 30 cây nến trên màn hình), biểu đồ có rất nhiều không gian trống. Việc người dùng phải rê chuột vào từng tam giác để xem % lãi/lỗ hoặc nhãn lý do thoát lệnh tạo thêm thao tác không cần thiết.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Hiển thị linh hoạt theo Mức độ Chi tiết (Level-of-Detail - LOD)**:
   - **Mức Thu nhỏ (Dense / High-level: $> 80$ nến hiển thị)**:
     - Chỉ vẽ icon tam giác tối giản 10px $\times$ 8px.
   - **Mức Trung bình (Medium: 30 - 80 nến hiển thị)**:
     - Vẽ icon tam giác + chấm chỉ báo giá thực thi.
   - **Mức Phóng to Cực đại (Ultra-detailed: $< 30$ nến hiển thị)**:
     - Bên cạnh icon tam giác, tự động vẽ thêm **Mini-badge % PnL** nhỏ gọn (ví dụ: `+2.1%` nền xanh nhạt hoặc `-0.9%` nền đỏ nhạt) và nhãn ngắn (`TP`, `SL`, `Sig`).
2. **Không gây xé hình hay giật lag**:
   - Quá trình chuyển đổi giữa các trạng thái LOD diễn ra tức thì trong chu kỳ `refresh_window()` của `MarkerLayer` / C++ native renderer.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng LOD & Viewport Windowing
- `marker_lod.py`:
  - Mở rộng hàm `select_marker_display()` để xác định `MarkerDensityMode` (DENSE, MEDIUM, DETAILED) dựa trên tỷ lệ `visible_candles_count = max_x_idx - min_x_idx`.
- `marker_layer.py` (`TriangleMarkerItem`):
  - Hỗ trợ vẽ kèm text item phụ khi ở chế độ `DETAILED`.
  - Tái sử dụng pool `TriangleMarkerItem` mà không tạo mới object liên tục khi zoom in/out.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1**: Khi zoom vào $< 30$ nến, mini-badge PnL tự động xuất hiện cạnh marker.
- [ ] **AC-2**: Khi zoom ra $> 80$ nến, badge PnL tự động ẩn đi và chỉ giữ icon tam giác.
- [ ] **AC-3**: Tỷ lệ FPS trong suốt quá trình zoom duy trì $\ge 60$ FPS.
- [ ] **AC-4**: Unit tests kiểm tra tính chính xác của thuật toán phân cấp LOD trong `test_marker_lod.py`.
