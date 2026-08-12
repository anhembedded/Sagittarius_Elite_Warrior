---
id: "BOT-018"
title: "Nhiệm vụ: Notifications / Alerting"
status: "backlog"
---

# Nhiệm vụ: Notifications / Alerting

## 1. Mục tiêu (Objective)
Cảnh báo người dùng khi có sự kiện quan trọng xảy ra trong lúc app chạy nền (sync lỗi, WebSocket stream mất kết nối, phát hiện gap dữ liệu) — hiện tại các lỗi này chỉ nằm trong log file, dễ bị bỏ sót nếu người dùng không mở app.

## 2. Mô tả (Description)
Tận dụng `IEventBus` đã có sẵn (dùng để phát `MarketTickEvent`, `BulkSyncEvents`...): thêm một `NotificationEventHandler` lắng nghe các sự kiện lỗi/cảnh báo hiện có và mới, hiển thị toast/banner trong UI, đồng thời hỗ trợ gửi qua kênh ngoài (Telegram Bot) khi app chạy headless/CLI.

## 3. Các bước thực hiện (Action Items)
- [ ] Rà soát các event hiện có (`BulkSyncEvents`, WebSocket reconnect trong `binance_websocket_service.py`) — bổ sung event còn thiếu nếu cần (vd `StreamDisconnectedEvent`, `DataGapDetectedEvent`) mà không phá vỡ hợp đồng hiện tại.
- [ ] `INotificationChannel` (port) với 2 implementation ban đầu: `UiToastNotificationChannel` (banner trong `MainWindow`/`DashboardView`) và `TelegramNotificationChannel` (dùng Bot Token từ config, chỉ kích hoạt nếu được cấu hình).
- [ ] `NotificationEventHandler` đăng ký qua `IEventBus`, map event → message, gọi channel(s) tương ứng.
- [ ] Cấu hình bật/tắt kênh Telegram qua `user_config.json` (`notifications.telegram.bot_token`, `notifications.telegram.chat_id`) — đọc qua `IConfig`, không hard-code.
- [ ] Unit test cho `NotificationEventHandler` (mock channel, assert đúng message cho từng loại event) theo `.agents/rules/testing.md`.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Không log/lưu Bot Token ra ngoài `user_config.json`.
- Lỗi gửi Telegram (mất mạng, token sai) không được làm crash luồng chính — bắt exception cục bộ trong channel, chỉ log cảnh báo.
- Cân nhắc rate-limit/debounce để tránh spam thông báo khi 1 sự kiện lỗi lặp lại liên tục (vd reconnect loop).
