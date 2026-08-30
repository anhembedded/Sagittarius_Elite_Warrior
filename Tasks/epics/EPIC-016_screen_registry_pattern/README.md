# Epic EPIC-016 — Screen Registry Pattern (xoá Hard Design trong `MainWindow`)

**Trạng thái:** 🟡 Đang làm — 2/4 task con xong (`016A`, `016B`). Cập nhật 2026-08-30.
**Nguồn:** Đề xuất kiến trúc của user, review kiến trúc trong phiên làm việc
2026-08-30, ratify ở [`DECISION_2026-08-30_screen_registry_pattern.md`](DECISION_2026-08-30_screen_registry_pattern.md).
**Thiết kế đầy đủ:** [`Docs/SCREEN-REGISTRY-PATTERN/README.md`](../../../Docs/SCREEN-REGISTRY-PATTERN/README.md) (v2.1).

---

## 1. Bối cảnh

`src/presentation/ui/main_window.py` hard-code hoàn toàn: `_NAV_SECTIONS`/
`_BOTTOM_ACTIONS` là hằng module-level, `_setup_router()` import trực tiếp
từng cặp Presenter/View của 4 màn hình (`dashboard`, `backtest`, `settings`,
`data_management`) và đăng ký thủ công vào `PresenterManager`. Thêm 1 màn
hình mới đòi sửa `MainWindow` ở ít nhất 2 chỗ.

Giải pháp: `ISidebar` (Protocol), `AbstractScreenModule` (ABC),
`IScreenRegistry` (port) + `ScreenRegistry` (adapter) — mỗi màn hình tự khai
báo route/nav metadata qua 1 `*ScreenModule`, `MainWindow` chỉ còn phụ thuộc
2 interface. Chi tiết đầy đủ ở tài liệu thiết kế; ADR chỉ ratify các câu hỏi
còn treo lại sau review (§10 của tài liệu thiết kế).

## 2. Task con

| ID | Tên | Rủi ro | Trạng thái |
| :--- | :--- | :---: | :---: |
| **[EPIC-016A](completed/EPIC-016A_xac_nhan_voi_engine_that.md)** | Xác nhận `PresenterManager.register()`/`ScreenDescriptor` với `Sagittarius_Engine` thật | 🟡 | ✅ Xong 2026-08-30 — chữ ký khớp thiết kế, `ScreenDescriptor` không tồn tại ở engine (đúng là định nghĩa mới ở Elite) |
| **[EPIC-016B](completed/EPIC-016B_registry_va_4_module.md)** | Dựng `registry/` (contracts + `ScreenRegistry`) + viết 4 `*ScreenModule` cho màn hiện có | 🔴 | ✅ Xong 2026-08-30 — 18 test xanh, đối chiếu byte-for-byte với nav cũ |
| **[EPIC-016C](incomplete/EPIC-016C_main_window_decouple.md)** | Đổi `MainWindow` nhận `IScreenRegistry`/`ISidebar`/`sidebar_factory` qua constructor, xoá hard-code | 🟡 | 🔴 Chưa bắt đầu — phụ thuộc `016B` |
| **[EPIC-016D](incomplete/EPIC-016D_bootstrapper_wiring.md)** | Cập nhật `app_bootstrapper.py` đăng ký 4 module + wiring `sidebar_factory` | 🟢 | 🔴 Chưa bắt đầu — phụ thuộc `016B`, `016C` |

**Thứ tự phụ thuộc:** `A` chặn `B` (không code registry trước khi biết chữ
ký engine thật). `B` chặn `C` và `D`. `C` và `D` có thể làm gần như song
song nhưng `D` cần `C` đã đổi xong constructor của `MainWindow` mới có gì để
gọi.

## 3. Không nằm trong epic này

- Thêm màn hình mới (Portfolio, Scanner, …) — chỉ là ví dụ minh hoạ, không
  phải việc cần làm ở epic này.
- Đổi UX/thứ tự hiển thị của 4 màn hình hiện có — migration phải giữ hành
  vi y hệt bản hard-code.
