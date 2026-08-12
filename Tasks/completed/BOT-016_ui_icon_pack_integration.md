---
id: "BOT-016"
title: "📋 BOT-016: Tích hợp Bộ Icon Pack Free (Lucide/Feather SVG từ GitHub) & Quản lý Assets UI"
status: "completed"
---

# 📋 BOT-016: Tích hợp Bộ Icon Pack Free (Lucide/Feather SVG từ GitHub) & Quản lý Assets UI

> [!IMPORTANT]
> **Độ ưu tiên:** 🔴 P0.9 (Hàng đầu Backlog — Cần thiết cho thiết kế UI chuyên nghiệp & nhất quán)  
> **Trạng thái:** ✅ Completed  
> **Lớp liên quan:** Presentation Layer (`src/presentation/ui/assets/icons/`, SVG Assets & IconLoader)  

---

## 1. 🎯 Mục tiêu (Objective)

Lựa chọn và tích hợp bộ Icon Pack free mã nguồn mở (vector SVG từ GitHub như **Lucide Icons** / **Feather Icons**). Tự động tải các file SVG chính thức từ GitHub repository về thư mục tài nguyên của dự án và xây dựng `IconLoader` để quản lý icon tập trung cho UI (`Sidebar`, `ControlCard`, `MonitorCard`, `Chart Toolbar`).

---

## 2. 📝 Mô tả Chi tiết (Description)

Hiện tại các nút bấm trên giao diện (`Sidebar`, `ControlCard`, `BaseCard`) chủ yếu sử dụng ký tự unicode hoặc văn bản thuần. Việc tích hợp một bộ icon nhất quán từ nguồn mã nguồn mở uy tín trên GitHub sẽ giúp ứng dụng đạt tiêu chuẩn giao diện ứng dụng tài chính/trading chuyên nghiệp.

---

## 3. 🛠️ Các bước Thực hiện (Action Items)

### Phase 1: Lựa chọn & Tải Icon Pack từ GitHub
- [x] **Lựa chọn Icon Set:** **Lucide Icons** (ISC/ MIT license cho các icon kế thừa từ Feather) — repository `lucide-icons/lucide`.
- [x] **Tải Icon Assets:** Tải 11 file SVG từ `raw.githubusercontent.com/lucide-icons/lucide/main/icons/` vào `src/presentation/ui/assets/icons/` — xem Ghi chú hoàn thành cho 3 tên bị đổi do Lucide đã rename icon.
- [x] **Xây dựng Helper `IconLoader`:** `src/presentation/ui/assets/icon_loader.py` — load SVG, cache theo `(name, color, size)`, recolor bằng cách thay thế `stroke="currentColor"`, palette `IconTheme` (vàng `#F3BA2F`, xanh `#0ECB81`, đỏ `#F6465D`, xám `#848E9C`), fallback về icon trong suốt khi thiếu file (không bao giờ raise exception).

### Phase 2: Gắn Icon vào các Component UI
- [x] **Sidebar Component:** `NavRoute` mở rộng thành `(label, route_name, icon_name)`; `layout-dashboard` cho Dev Board, `database` cho Database.
- [x] **Control Card Component:** `clock` (Load History), `play` màu xanh (Start Live), `square` màu đỏ (Stop).
- [x] **Monitor Card Component:** `trash-2` cho nút Clear; `append_log(message, level=...)` (mặc định `"info"`, backward-compatible với mọi lời gọi cũ) nhúng icon inline qua `<img>` base64 — `info`/`triangle-alert`/`circle-check-big` theo `level`.

### Phase 3: Unit Tests & Resource Management
- [x] **Unit Tests:** `tests/unit/presentation/ui/test_icon_loader.py` — tất cả 11 icon load thành công, caching theo key, cache tách theo màu, fallback khi thiếu file, `get_icon_data_uri()`, singleton `get_icon_loader()`.

---

## 4. ⚠️ Rủi ro & Lưu ý (Constraints & Risks)

> [!TIP]
> Sử dụng định dạng vector **SVG** nguyên bản từ GitHub để icon hiển thị sắc nét trên mọi độ phân giải màn hình (FullHD, 2K, 4K Retina) và dễ dàng đổi màu sắc tương thích Dark Theme.

## 5. Ghi chú hoàn thành (Completion Notes)

- **3 icon đã bị Lucide đổi tên** so với tên gốc trong task doc (kiểm tra HTTP 404 trước khi tải): `history` → **`clock`**, `check-circle-2` → **`circle-check-big`**, `candlestick-chart` → **`chart-candlestick`**.
- `settings.svg` và `chart-candlestick.svg` đã tải về nhưng **chưa gắn vào component nào** — chưa có màn hình Settings hay Chart Toolbar cụ thể để gắn (Toolbar thuộc BOT-010, chưa làm). Giữ lại trong `assets/icons/` sẵn cho khi cần.
- Đã tải `LICENSE.txt` (ISC License, bản gốc từ `lucide-icons/lucide`) vào `assets/icons/` để giữ đúng attribution.
- Icon nhúng vào log (`MonitorCard.append_log`) dùng `<img>` base64 data URI thay vì icon Unicode — QTextEdit không có khái niệm QIcon, chỉ resolve được image source.
- Verify: `scripts/ci-local.ps1` (ruff lint, ruff format, 123 tests) pass.
