# PROP-001: Đường Nối Lệnh Vào - Ra (Trade Entry-Exit Connection Line on Hover & Selection)

- **ID**: `PROP-001`
- **Type**: Proposal / UX Enhancement
- **Module**: `Backtest Screen / ChartCard / NativeChart`
- **Status**: `Backlog`
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

Hiện tại, các điểm vào lệnh (Entry) và đóng lệnh (Exit) trên biểu đồ Backtest được biểu diễn bằng các icon tam giác nhỏ gọn (▲ xanh lá và ▼ đỏ). Khi một chiến lược thực hiện nhiều giao dịch trong một khoảng thời gian dài hoặc khi thị trường biến động mạnh, việc xác định bằng mắt thường điểm vào lệnh nào tương ứng với điểm đóng lệnh nào đòi hỏi người dùng phải rê chuột xem từng tooltip hoặc đối chiếu thời gian thủ công với bảng Trade Logs.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Hiển thị trực quan chu kỳ lệnh**: Khi người dùng hover chuột vào một marker (tam giác vào lệnh hoặc đóng lệnh) hoặc khi một hàng trong bảng Trade Logs đang được chọn, biểu đồ sẽ vẽ một đường nét đứt (*dashed link line*) nối trực tiếp giữa:
   - Điểm vào lệnh: `(entry_time, entry_price)`
   - Điểm đóng lệnh: `(exit_time, exit_price)`
2. **Màu sắc theo kết quả PnL**:
   - Trade thắng ($PnL > 0$): Đường nét đứt màu xanh lá `#0ECB81` với độ mờ tinh tế (alpha ~0.7).
   - Trade thua ($PnL \le 0$): Đường nét đứt màu đỏ `#F6465D` với độ mờ tinh tế (alpha ~0.7).
3. **Mini-badge / Tooltip thông minh trên đường nối**:
   - Khi hover vào chính đường nối: Hiển thị tóm tắt thời lượng giữ lệnh (*holding duration*) và tỷ lệ lợi nhuận `+2.35% (+$420.00)`.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng Clean Architecture
- **Domain**: Giữ nguyên `Trade` và `BacktestResult` (đã có đủ `entry_time`, `entry_price`, `exit_time`, `exit_price`, `pnl`).
- **Presentation (Python PyQtGraph)**:
  - Bổ sung `TradeLinkLayer` hoặc mở rộng `MarkerLayer` trong `src/presentation/ui/components/chart_card/` sử dụng `QGraphicsPathItem` với `QPen(Qt.DashLine)`.
  - Quản lý trạng thái `active_hovered_trade_id` hoặc `selected_trade_index`.
- **Presentation (Native C++ QSG)**:
  - Bổ sung node vẽ line geometry trong `NativeChartItem` cho trade đang được hover/focus.

### 3.2. Hiệu năng & Render
- Đường nối chỉ được vẽ khi có tương tác hover / selection (tối đa 1-2 đường tại một thời điểm), không vẽ đồng loạt hàng trăm đường cùng lúc để tránh rác biểu đồ và bảo toàn 60 FPS.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1**: Khi hover vào marker Entry hoặc Exit, đường nét đứt nối với marker đối ứng xuất hiện ngay lập tức (< 16ms).
- [ ] **AC-2**: Màu sắc đường nối phản ánh chính xác kết quả trade (xanh lá cho Win, đỏ cho Loss).
- [ ] **AC-3**: Khi di chuyển chuột ra ngoài marker, đường nối biến mất mượt mà.
- [ ] **AC-4**: Khi chọn 1 hàng trong bảng Trade Logs, đường nối của trade tương ứng được kích hoạt trên chart.
- [ ] **AC-5**: Đầy đủ unit tests cho `TradeLinkLayer` và tương tác hover / selection.
