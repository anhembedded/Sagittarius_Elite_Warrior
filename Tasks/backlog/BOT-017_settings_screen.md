---
id: "BOT-017"
title: "Nhiệm vụ: Settings Screen (Cấu hình qua UI)"
status: "backlog"
---

# Nhiệm vụ: Settings Screen (Cấu hình qua UI)

## 1. Mục tiêu (Objective)
Cho phép người dùng xem/sửa các cấu hình quan trọng (API Key/Secret, danh sách symbol mặc định, interval mặc định, số ngày sync mặc định, theme) trực tiếp qua UI thay vì sửa tay `user_config.json`, giảm rủi ro gõ sai JSON làm hỏng app khi khởi động.

## 2. Mô tả (Description)
Thêm màn hình `SettingsScreen` mới vào Sidebar (cạnh Dashboard/Data Management), theo đúng kiến trúc `Presenter` + `View` hiện có (`dashboard/`, `data_management/`). Đọc/ghi cấu hình qua `IConfig` (đã có trong `sagittarius_engine`) — không tự chế cơ chế đọc/ghi file JSON riêng.

## 3. Các bước thực hiện (Action Items)
- [ ] `SettingsView`: form các trường `API_KEY`/`API_SECRET` (masked input), `DEFAULT_SYMBOLS`, `DEFAULT_INTERVAL`, `DEFAULT_SYNC_DAYS`.
- [ ] `SettingsPresenter`: đọc giá trị hiện tại từ `IConfig` khi mở màn hình; validate input tối thiểu (symbol không rỗng, sync days > 0) trước khi ghi.
- [ ] Nút "Save" ghi lại `user_config.json` qua `IConfig`; hiển thị thông báo cần khởi động lại app nếu cấu hình đó chỉ được đọc lúc boot (vd API key dùng để tạo `PythonBinanceClient`).
- [ ] Đăng ký route/sidebar entry mới, dùng icon có sẵn từ `IconLoader` (`settings` đã có trong bộ Lucide đã tích hợp ở BOT-016).
- [ ] Unit test cho `SettingsPresenter` (đọc/ghi/validate) theo `.agents/rules/testing.md`.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Không log giá trị `API_SECRET` ra console/log file dưới bất kỳ hình thức nào.
- Ô nhập API Secret phải che (password field), không hiển thị plaintext mặc định.
- Một số cấu hình (vd API key) chỉ có hiệu lực sau khi khởi động lại tiến trình — cần nói rõ trong UI, không giả vờ là "hot reload" nếu chưa thực sự làm được.
