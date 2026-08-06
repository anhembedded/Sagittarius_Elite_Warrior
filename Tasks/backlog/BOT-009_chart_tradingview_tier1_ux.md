# Nhiệm vụ: TradingView Chart Enhancements - Tier 1 (Core UX & Volume)

## 1. Mục tiêu (Objective)
Nâng cấp trải nghiệm tương tác biểu đồ (`chart_card/`) tiệm cận TradingView bằng cách bổ sung các tính năng UX cốt lõi có giá trị cao và chi phí phát triển thấp - vừa.

## 2. Mô tả (Description)
Hiện tại `chart_card/` chỉ mới hỗ trợ vẽ nến cơ bản, pan/zoom mặc định và crosshair. Nhiệm vụ này tập trung vào hiển thị thông tin giá/volume rõ ràng, cải thiện crosshair và quản lý indicator.

## 3. Các bước thực hiện (Action Items)
- [ ] **Volume Bars dưới nến:** Cập nhật `IndicatorManager.add_volume(...)` dùng `pg.BarGraphItem` hiển thị cột volume theo màu tăng (xanh) / giảm (đỏ) của nến.
- [ ] **Last Price Line:** Tạo component `price_line.py` vẽ đường ngang đứt nét (dashed line) + nhãn hiển thị giá hiện tại real-time trên trục Y.
- [ ] **OHLC Info Box khi Hover:** Mở rộng `CrosshairController` tra cứu thông số nến tại vị trí con trỏ `(x, y)` và hiển thị thông tin Open / High / Low / Close / %Change trên header/overlay.
- [ ] **Viewport Auto-Follow & "Jump to Live":** Tạo `viewport_controller.py` phát hiện khi người dùng pan lịch sử nến; hiển thị nút nổi **"⏵ Live"** để nhảy nhanh về nến mới nhất mà không bị kéo giật tự động.
- [ ] **Remove & Toggle Indicator:** Bổ sung các phương thức `remove(name)` và `set_visible(name, bool)` trong `IndicatorManager`.
- [ ] **Legend trên Subplot:** Hiển thị nhãn legend nhỏ trên góc plot (Tên chỉ báo, giá trị cuối cùng, nút ẩn/xóa).

## 4. Kiến trúc & Vị trí Mã nguồn (Architectural Context)
- `Binace_Bot/src/presentation/ui/components/chart_card/`
- Pattern: Component-based composition gắn trực tiếp vào `PyQtGraph` scene/view.
