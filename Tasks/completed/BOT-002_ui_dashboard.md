---
id: "BOT-002"
title: "Phase 5: UI Dashboard (Simple Demo)"
status: "completed"
---

# Phase 5: UI Dashboard (Simple Demo)

- **Status**: 🟡 In Progress
- **Category**: Presentation Layer (Web GUI)

## 🎯 Goal
Xây dựng một giao diện Web đơn giản (Web Dashboard Demo) bằng Streamlit để trực quan hóa dữ liệu từ Bot, thay vì chỉ thao tác trên CLI.

Yêu cầu cụ thể:
1. Load dữ liệu lịch sử từ Database (SQLite) thông qua tầng Application/Infrastructure hiện tại.
2. Vẽ biểu đồ nến thời gian thực (Realtime Plot) bằng Plotly.
3. Cho phép người dùng tương tác (chọn cặp tiền, chọn khung thời gian).
4. (Tùy chọn) Giao tiếp với Bot qua Websocket/Event để cập nhật nến liên tục.

## 📋 Checklist

- [ ] Setup môi trường: Install `streamlit`, `plotly`, `pandas`.
- [ ] Khởi tạo thư mục `src/presentation/ui` và cấu trúc file.
- [ ] Viết script khởi chạy `streamlit run ...`.
- [ ] Kết nối UI với Application Layer (hoặc qua HTTP/Event) để kéo dữ liệu.
- [ ] Hiển thị biểu đồ nến (Candlestick chart).
- [ ] Thêm các nút điều khiển (Selectbox, Button).
