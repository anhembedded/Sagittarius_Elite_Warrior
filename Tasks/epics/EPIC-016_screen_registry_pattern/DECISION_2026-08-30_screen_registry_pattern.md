# ADR — Screen Registry Pattern: Tách `MainWindow` khỏi Hard Design

**Thuộc Epic:** [`EPIC-016`](README.md)
**Ngày:** 2026-08-30
**Trạng thái:** 🟢 **Approved** — ratify các câu hỏi mở ở
[`Docs/SCREEN-REGISTRY-PATTERN/README.md`](../../../Docs/SCREEN-REGISTRY-PATTERN/README.md)
§10. D4 đã ✅ Established (2026-08-30, xem `EPIC-016A`) — `EPIC-016B` mở khoá.

> [!IMPORTANT]
> Đọc cột trạng thái, không đọc văn xuôi.
>
> | Nhãn | Ý nghĩa |
> | :--- | :--- |
> | ✅ **Established** | Đã xác nhận trên cây code thật; trích `file:line` |
> | 🔵 **Proposed** | Đã chốt trong phiên review; **chưa** implement |
> | ❓ **Open** | Chặn implementation cho tới khi trả lời |

---

## 1. Bối cảnh

`src/presentation/ui/main_window.py` hard-code toàn bộ: `_NAV_SECTIONS`/
`_BOTTOM_ACTIONS` là hằng module-level, `_setup_router()` import trực tiếp 4
cặp Presenter/View và đăng ký thủ công. Thêm 1 màn hình mới đòi sửa
`MainWindow` ở ít nhất 2 chỗ. ✅ Established.

User đề xuất **Screen Registry Pattern V2** (`ISidebar` Protocol,
`AbstractScreenModule` ABC, `IScreenRegistry` port, Section/Item Sequence
hai tầng) để giải quyết. Bản thiết kế đầy đủ đã ghi ở
[`Docs/SCREEN-REGISTRY-PATTERN/README.md`](../../../Docs/SCREEN-REGISTRY-PATTERN/README.md)
(v2.1, đã qua 1 vòng review kiến trúc, mục 10 để lại 5 câu hỏi mở). ADR này
**không lặp lại** nội dung thiết kế — chỉ ratify các câu hỏi còn treo để có
thể mở task implementation.

---

## 2. Quyết định

### D1 — Không tạo type song song với `ITab`/`SidebarSection` cho ranh giới Sidebar ✅ Established → 🔵 Proposed

`components/sidebar/` đã có `ITab` (Protocol, `runtime_checkable`) và
`SidebarSection` (title + `tuple[ITab, ...]`) — đúng cấu trúc hai tầng mà
thiết kế V2 cần. `NavItem`/`NavSection` trong tài liệu thiết kế **đã** là
alias tương thích ngược của 2 type này (không phải type mới).

**Quyết định:** `NavMetadata`/`SectionDescriptor` chỉ tồn tại **nội bộ
`ScreenRegistry`** — chúng mang thêm field mà `ITab`/`SidebarSection` không
cần biết (`section_sequence`, `item_sequence`, ownership). Ranh giới công
khai tới `ISidebar.set_navigation()` **bắt buộc** vẫn là `SidebarSection`/
`ITab` nguyên bản (qua alias `NavSection`/`NavItem`) — không type mới nào
lộ ra ngoài registry. `ScreenRegistry.build_sidebar_navigation()` là nơi
chuyển đổi.

### D2 — Quyền sở hữu `section_sequence`: fail fast khi xung đột 🔵 Proposed

Khi nhiều `AbstractScreenModule` cùng khai `section_key` nhưng
`section_sequence` khác nhau, và không có `register_section()` khai tường
minh: **raise `ValueError`** ngay tại `register_module()`, không âm thầm
lấy giá trị module đăng ký trước. `register_section()` gọi tường minh luôn
là nguồn sự thật duy nhất khi đã gọi.

### D3 — Ngữ nghĩa `select_section()`: không exclusive-accordion ở v1 🔵 Proposed

`select_section(section_key)` mở rộng đúng 1 section được chỉ định, **không**
tự thu gọn các section khác (không phải accordion loại trừ lẫn nhau). Gọi
trên section có `is_collapsible=False` là no-op (không raise). Accordion loại
trừ lẫn nhau, nếu cần, là quyết định riêng cho lần sau khi số lượng section
thực sự đòi hỏi — không xây trước khi có nhu cầu thật (đúng tinh thần
"cấm speculative generality" của repo).

### D4 — Xác nhận với `Sagittarius_Engine` thật trước khi code ✅ Established (2026-08-30)

`PresenterManager.register()` được `i_state_contributor.py` ghi chú là
**cố ý duck-typed**. Xác nhận bằng cách clone engine thật
(`anhembedded/sagittarius_engine`, commit `c8b1862`) — xem
[`EPIC-016A`](completed/EPIC-016A_xac_nhan_voi_engine_that.md):

1. `presenter_manager.py:38-54` — `register(name, presenter_class, view_factory)`;
   lúc lazy-load gọi `view_factory()` (0 tham số) và
   `presenter_class(view, container)` — khớp chính xác thiết kế gốc.
2. `ScreenDescriptor` **không tồn tại** ở engine — Elite định nghĩa mới là
   đúng, không lặp hợp đồng.
3. Engine pin `2.3.0`, khớp version Elite đang dùng — không cần bump.

`EPIC-016B` mở khoá.

### D5 — Hợp đồng lỗi của `IScreenRegistry` 🔵 Proposed

- `get(route)` không tìm thấy → raise `KeyError(route)`.
- `get_default_route()` chưa có module nào khai `is_default=True` → raise
  `RuntimeError("no ScreenModule declared is_default=True")`.
- `register()`/`register_module()` trùng route → raise `ValueError` (đã có
  sẵn trong bản thiết kế, giữ nguyên).

### D6 — `ISidebar` là `Protocol`, lý do (b) — không phải (a) 🔵 Proposed

`Sidebar` đã kế thừa `BaseView` (engine, `QObject`-based) → không thể thêm
`ABC` làm base thứ 2. Đây là lý do **(b)** trong `architecture-rule.md`
§2.1 ("NO Multiple Inheritance" chặn), cùng tiền lệ với `ITab`. Docstring
của `ISidebar` phải ghi lý do này bằng đúng câu chữ, không diễn giải chung
chung kiểu "Shiboken metaclass". Vì `presentation/` không có cổng mypy,
`ISidebar` **bắt buộc** có test hợp đồng hai chiều (đối chiếu chữ ký với
`Sidebar`), tiền lệ `test_backtest_view_contract.py`.

---

## 3. Hệ quả

**Được:** `MainWindow` hết phụ thuộc concrete screen; thêm màn hình mới chỉ
cần 1 file `module.py` + 1 dòng đăng ký ở bootstrapper — đúng mục tiêu gốc.

**Trả giá:** Phải migrate đồng thời cả 4 màn hình hiện có (`dashboard`,
`backtest`, `settings`, `data_management`) trong cùng 1 đợt vì
`AbstractScreenModule`/`IScreenRegistry` là `ABC` thật — không làm dở dang
được. `EPIC-016B` do đó là task lớn nhất, gộp cả 4 module + registry.

**Không đổi:** Hành vi UX của 4 màn hình hiện có (nav order, default route,
bottom actions) phải giữ nguyên y hệt bản hard-code — đây không phải dịp
đổi UX.

---

## 4. Ngoài phạm vi (rõ ràng)

- Accordion loại trừ lẫn nhau cho `select_section()` (xem D3).
- Thêm màn hình mới ngoài 4 màn hiện có (Portfolio, Scanner, …) — chỉ là ví
  dụ minh hoạ trong tài liệu thiết kế, không nằm trong scope epic này.
- Đổi cách `PresenterManager` hoạt động ở phía engine.

---

## 5. Tham chiếu

- [`Docs/SCREEN-REGISTRY-PATTERN/README.md`](../../../Docs/SCREEN-REGISTRY-PATTERN/README.md) — thiết kế đầy đủ, v2.1
- `.agents/rules/architecture-rule.md` §2.1 — quy tắc ABC vs Protocol
- [`EPIC-013`](../EPIC-013_hop_dong_tuong_minh_va_tach_coordinator/README.md) — tiền lệ `ITab`/hợp đồng tường minh
- `src/presentation/ui/state/i_state_contributor.py` — ghi chú `PresenterManager.register()` cố ý duck-typed
