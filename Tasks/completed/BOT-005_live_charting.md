---
id: "BOT-005"
title: "Nhiệm vụ: Tích hợp Vẽ Biểu Đồ (Live Charting) Real-time"
status: "completed"
---

# Nhiệm vụ: Tích hợp Vẽ Biểu Đồ (Live Charting) Real-time

## 1. Mục tiêu (Objective)
Cập nhật đồ thị nến/chỉ báo ngay tức thì trên giao diện Dashboard dựa trên tín hiệu WebSocket từ sàn giao dịch, tạo hiệu ứng phản hồi cực tốt cho người dùng (WOW effect).

## 2. Mô tả (Description)
Hệ thống kết nối luồng (Stream) qua WebSocket hiện đã thu thập tín hiệu thành công và ném ra các `MarketTickEvent`.
Chúng ta cần lắng nghe các sự kiện này tại tầng giao diện (UI) và đẩy dữ liệu vào module biểu đồ của PyQtGraph.

## 3. Các bước thực hiện (Action Items)
- [ ] Ở `DashboardPresenter`, lắng nghe sự kiện từ `MarketTickEvent` của `app.event_bus`.
- [ ] Điều hướng dữ liệu Tick (thời gian, giá Open, High, Low, Close) vào giao diện để không block Main UI Thread (phải chuyển qua Qt Signals/Slots).
- [ ] Cập nhật đồ thị nến trong `ChartCard` mỗi khi có tick mới để nến dịch chuyển/nhấp nháy mượt mà.
- [ ] Bổ sung các chỉ báo (Moving Average, RSI, v.v) nếu cần thiết để UI thêm trực quan.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Market tick có thể gửi dữ liệu tần suất cực cao. Việc vẽ lại toàn bộ đồ thị (re-draw) liên tục có thể gây đứng UI. Cần phải tối ưu hoá cơ chế "vẽ nối thêm" thay vì xoá trắng vẽ lại.
