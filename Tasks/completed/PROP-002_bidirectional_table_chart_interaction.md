# PROP-002: Tương Tác Hai Chiều Bảng Trade Logs & Biểu Đồ (Bi-directional Table-to-Chart Navigation & Highlighting)

- **ID**: `PROP-002`
- **Type**: Proposal / UX Enhancement
- **Module**: `Backtest Screen / Trade Logs / ChartCard`
- **Status**: `Backlog`
- **Target Version**: `Backtest UX Polish`

---

## 1. Bối cảnh & Vấn đề (Context & Problem)

Hiện tại, bảng **Trade Logs** (danh sách lịch sử lệnh) và **Chart Canvas** (biểu đồ nến & markers) hoạt động tương đối độc lập về mặt tương tác người dùng:
- Khi người dùng muốn xem lại một lệnh bị lỗ nặng hoặc lãi lớn trên bảng Trade Logs, họ phải tự cuộn trục thời gian trên biểu đồ để tìm thời điểm diễn ra lệnh đó.
- Khi người dùng nhìn thấy một cụm marker trên biểu đồ và muốn tra cứu chi tiết thông số lý do vào/ra lệnh, họ phải lật qua các trang phân trang của bảng Trade Logs để tìm dòng tương ứng.

---

## 2. Mục tiêu Đề xuất (Proposal Goals)

1. **Điều hướng từ Bảng sang Biểu đồ (Table $\rightarrow$ Chart)**:
   - Khi người dùng click chọn 1 hàng trong bảng `Trade Logs`, biểu đồ tự động thực hiện cuộn mượt mà (*smooth pan/zoom*) để đưa cây nến Entry & Exit của lệnh đó vào trung tâm màn hình.
   - Làm nổi bật (*pulse animation* hoặc *ring highlight*) cặp marker tương ứng trên chart trong 2 giây.
2. **Điều hướng từ Biểu đồ sang Bảng (Chart $\rightarrow$ Table)**:
   - Khi người dùng click vào một tam giác marker trên biểu đồ:
     - Bảng `Trade Logs` tự động chuyển đến đúng trang phân trang (*page number*) chứa lệnh đó.
     - Tự động cuộn và bôi sáng hàng tương ứng trong bảng.

---

## 3. Thiết kế Kỹ thuật (Technical Design)

### 3.1. Phân tầng Clean Architecture & Signals
- **ViewModel (`backtest_view_model.py`)**:
  - Khai báo thuộc tính `@Property(int)` `focusedTradeIndex` và signal `focusedTradeChanged`.
  - Khai báo `@Slot(int)` `focusTrade(int index)` được gọi từ QML table delegate hoặc chart interaction.
- **Presenter (`backtest_presenter.py`)**:
  - Nhận sự kiện `focusTrade`:
    - Tính toán phạm vi timestamp `(min_ts, max_ts)` của trade.
    - Gọi `chart_card.set_view_range(min_ts - padding, max_ts + padding)`.
    - Tính toán số trang phân trang: `target_page = (index // PAGE_SIZE) + 1` và cập nhật `tradeLogCurrentPage`.
- **QML Views**:
  - `BackTestTradeLogs.qml`: Bind highlight delegate với `viewModel.focusedTradeIndex`.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1**: Click vào hàng trong `Trade Logs` điều hướng biểu đồ đến đúng thời gian của lệnh với biên đệm 10% an toàn.
- [ ] **AC-2**: Click vào marker trên biểu đồ tự động chuyển bảng `Trade Logs` đến đúng trang và chọn đúng hàng.
- [ ] **AC-3**: Tương tác mượt mà, không bị giật lag, không reload lại dữ liệu hay kích hoạt lại FSM.
- [ ] **AC-4**: Kiểm thử đầy đủ với Unit test (Presenter/ViewModel slot signal) và Sanity test.
