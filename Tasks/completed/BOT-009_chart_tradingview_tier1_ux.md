---
id: "BOT-009"
title: "Nhiệm vụ: TradingView Chart Enhancements - Tier 1 (Core UX & Volume)"
status: "completed"
---

# Nhiệm vụ: TradingView Chart Enhancements - Tier 1 (Core UX & Volume)

## 1. Mục tiêu (Objective)
Nâng cấp trải nghiệm tương tác biểu đồ (`chart_card/`) tiệm cận TradingView bằng cách bổ sung các tính năng UX cốt lõi có giá trị cao và chi phí phát triển thấp - vừa.

## 2. Mô tả (Description)
Hiện tại `chart_card/` chỉ mới hỗ trợ vẽ nến cơ bản, pan/zoom mặc định và crosshair. Nhiệm vụ này tập trung vào hiển thị thông tin giá/volume rõ ràng, cải thiện crosshair và quản lý indicator.

## 3. Các bước thực hiện (Action Items)
- [x] **Volume Bars dưới nến:** `VolumeItem` (`volume_renderer.py`) dùng `pg.BarGraphItem` hiển thị cột volume theo màu tăng (xanh) / giảm (đỏ) của nến, cùng vòng đời historical/live/closed như `FastCandlestickItem`.
- [x] **Last Price Line:** `LastPriceLine` (`price_line.py`) vẽ đường ngang đứt nét (dashed line) + nhãn hiển thị giá hiện tại real-time trên trục Y, đổi màu theo tăng/giảm.
- [x] **OHLC Info Box khi Hover:** `CrosshairController` nhận `ohlc_lookup` callback, tra cứu nến gần nhất tại vị trí con trỏ trên plot chính và hiển thị Open / High / Low / Close / %Change trên label; các plot phụ (subplot) vẫn giữ label Time/Value như cũ.
- [x] **Viewport Auto-Follow & "Jump to Live":** `ViewportController` (`viewport_controller.py`) lắng nghe `ViewBox.sigRangeChangedManually` để phát hiện pan/zoom thủ công của người dùng, dừng auto-follow và hiện nút nổi **"⏩ Live"**; nút này (và `resume_follow()`) đưa view quay lại theo dõi nến mới nhất.
- [x] **Remove & Toggle Indicator:** `IndicatorManager.set_visible(name, bool)` và `remove(name)` đã bổ sung, expose qua `ChartCard.set_indicator_visible()` / `remove_indicator()`.
- [x] **Legend trên Subplot:** Dùng `pg.LegendItem`/`plot.addLegend()` có sẵn của pyqtgraph — mỗi indicator có 1 dòng legend (tên + giá trị cuối, cập nhật mỗi tick). Click vào swatch màu để ẩn/hiện (hành vi built-in của `ItemSample`, tương đương `set_visible`).

## 4. Kiến trúc & Vị trí Mã nguồn (Architectural Context)
- `Binace_Bot/src/presentation/ui/components/chart_card/`
- Pattern: Component-based composition gắn trực tiếp vào `PyQtGraph` scene/view.

## 5. Ghi chú hoàn thành (Completion Notes)
- `dashboard_presenter.py` được nối dây để đẩy `MarketData.volume` (vốn đã có trong domain nhưng chưa từng lên UI) qua `ui_chart_update_signal` / `ui_history_reloaded_signal` — nếu không Volume Bars sẽ không có dữ liệu thật.
- **Sai khác nhỏ so với đặc tả:** mục Legend chỉ có nút **ẩn/hiện** (native pyqtgraph click-to-toggle), chưa có nút **xóa** ngay trên canvas — `remove(name)` hiện là API lập trình (gọi từ code), chưa có affordance click-để-xóa trong legend. Lý do: hand-rolled click hit-testing trong `QGraphicsScene` rủi ro cao hơn giá trị mang lại ở Tier 1; nút xóa trực quan nên đặt trong toolbar quản lý indicator ở Tier 2/3.
- Verify: `scripts/ci-local.ps1` (ruff lint, ruff format, 98 tests) pass.
