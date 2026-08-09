## User Story dạng developer

### US-01: Thêm menu chọn Indicator trên Dev Board
As a developer, I want to open an Indicator selector on the Dev Board and choose from the available indicator definitions, so that I can enable or disable chart overlays/subplots during UI development and testing.

Acceptance Criteria:
- Có nút Indicator trên Dev Board.
- Khi click, hiển thị sub-window chứa danh sách indicator hiện có.
- Người dùng có thể bật/tắt từng indicator.
- Indicator được render lên chart nếu đang enabled.
- Nếu danh sách indicator rỗng hoặc không hợp lệ, hệ thống hiển thị trạng thái lỗi rõ ràng.

### US-02: Thêm menu chọn Strategy trên Dev Board
As a developer, I want to toggle Strategy and choose from the current strategy list, so that I can validate strategy behavior and indicator composition in the chart UI.

Acceptance Criteria:
- Có nút Strategy trên Dev Board.
- Có toggle bật/tắt cho từng strategy.
- Strategy list được render trong sub-window.
- Strategy kế thừa từ indicator logic và sử dụng cùng cơ chế enable/disable.
- Khi bật strategy, UI cập nhật state và render tương ứng.
- Khi tắt strategy, state bị xóa khỏi chart mà không cần reload toàn bộ màn hình.

---

## User Story cho data loading

### US-03: Auto-load 75 candle theo timeframe đang chọn
As a developer, I want the Dev Board to automatically load the last 75 candles for the selected timeframe, so that the chart can be tested quickly without a manual history load step.

Acceptance Criteria:
- Khi mở Dev Board hoặc đổi timeframe, hệ thống tự động load 75 cây nến.
- Timeframe mặc định hoặc đang chọn được dùng để fetch dữ liệu.
- Nếu DB thiếu dữ liệu, hệ thống auto-sync từ Binance.
- Dữ liệu được cache để tránh reload không cần thiết.
- Data và indicator được render cùng lúc khi sẵn sàng.

### US-04: Load thêm 75 candle khi rollback - hoặc zoom.
As a developer, I want the chart to request additional historical candles when the user scrolls backward, so that I can test pagination and historical expansion behavior.

Acceptance Criteria:
- Khi user rollback / kéo ngược về trước, hệ thống tự động load thêm 75 nến (hoặc là thực toán nào đó đã được kiểm chứng)
- Nếu dữ liệu thiếu trong đoạn rollback, hệ thống sync dữ liệu trước khi render tiếp.
- Indicator state được giữ nguyên sau khi load thêm dữ liệu.
- Không làm duplicate data hoặc phá vỡ state của chart.

---

## User Story cho timeframe selector component

### US-05: Tách timeframe selector thành component riêng
As a developer, I want the timeframe selector to be a standalone reusable component, so that the chart UI can switch between intervals in a consistent and testable way.

Acceptance Criteria:
- Timeframe list bao gồm: 1m, 5m, 15m, 1h, 1d.
- Có thể mở rộng thêm timeframe khác trong tương lai.
- Component này được include trực tiếp vào chart view.
- Khi timeframe thay đổi, component phát ra signal với state mới.
- Presenter/chart logic nhận state và trigger refresh tương ứng.

### US-06: Timeframe change phải là signal-driven state
As a developer, I want timeframe changes to be driven by a signal/state contract, so that the chart and presenter remain decoupled and testable.

Acceptance Criteria:
- Timeframe change phát ra signal có state mới.
- Presenter xử lý việc reload dữ liệu và refresh indicators.
- Không hardcode logic trong QML hoặc view component.
- State và event được kiểm tra bằng unit/integration test.

---

## User Story cho indicator default

### US-07: Indicator mặc định là EMA 200/100/50/20
As a developer, I want default EMA indicators to be available and enabled for the Dev Board, so that the chart can test standard trend overlays without manual setup.

Acceptance Criteria:
- Các indicator mặc định gồm: EMA 200, EMA 100, EMA 50, EMA 20.
- Mỗi indicator có nút enable/disable.
- Indicator được load từ default indicator scripts:
  - /default_indicator/Ema_200.py
  - /default_indicator/Ema_100.py
  - /default_indicator/Ema_50.py
  - /default_indicator/Ema_20.py
- Nếu script không tồn tại hoặc lỗi, UI báo trạng thái lỗi mà không crash.
- Khi enabled, indicator render lên chart cùng với dữ liệu lịch sử.

---

## User Story cho bỏ Load Hist

### US-08: Bỏ nút Load Hist và dùng workflow auto start chart
As a developer, I want the Dev Board to start chart setup automatically with history load, data sync, and live streaming, so that the screen behaves like a unified test environment.

Acceptance Criteria:
- Nút Load Hist bị bỏ.
- Khi chart start, hệ thống tự động:
  1. load lịch sử
  2. sync missing candles
  3. start live stream
- Nếu live stream đang chạy, không start lại trùng lặp.
- Nếu sync lỗi, trạng thái lỗi được hiển thị rõ.
- Flow này hoạt động qua event/state machine chuẩn.

---

