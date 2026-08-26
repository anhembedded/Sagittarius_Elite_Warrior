# BUG-054 — Màn hình Settings vỡ hoàn toàn: `StyleRole` không có `HEADING` (và `BODY_LABEL`)

**Reported date:** 2026-08-26
**Severity:** Chưa đánh giá (nhưng màn hình Settings **không dựng được**, tức là route `settings` chết hẳn)
**Status:** 🔴 Mở — **chỉ ghi nhận hiện tượng theo yêu cầu, chưa điều tra root cause**
**Found by:** chạy regression trong lúc làm `EPIC-010C` (không liên quan tới EPIC-010)

---

## Hiện tượng

Mọi đường đi tới route `settings` đều ném:

```
File "src/presentation/ui/screens/settings/settings_view.py", line 233, in _build_header
    apply_role(title, StyleRole.HEADING)
AttributeError: type object 'StyleRole' has no attribute 'HEADING'
```

Exception bay ra từ `SettingsView.__init__` → `_build_ui()` → `_build_header()`,
tức là **ngay lúc dựng view**, trước khi user kịp thao tác gì.

## Test đang đỏ vì lỗi này

| Test | Kiểu |
| :--- | :--- |
| `tests/sanity/test_composition_root.py::test_every_navigable_route_constructs[settings]` | FAILED |
| `tests/integration/presentation/ui/test_sanity_ui_e2e.py::test_sanity_settings_screen_save` | FAILED + ERROR |

Đây là 2 test đỏ duy nhất còn lại trong bộ regression của `EPIC-010`
(72 passed / 2 failed) — không phải do EPIC-010 gây ra.

## Quan sát đã có (chưa phải root cause)

Ghi lại đúng những gì đã nhìn thấy, **chưa** truy nguyên nhân:

1. **Có 2 call site hỏng, không phải 1.** Test chỉ chạm cái đầu tiên rồi dừng:
   - `settings_view.py:233` → `StyleRole.HEADING`
   - `settings_view.py:308` → `StyleRole.BODY_LABEL`
2. `StyleRole` (định nghĩa trong **Engine**, không phải app:
   `sagittarius_engine/extensions/pyside_mvc/widgets/style.py`) trong bản
   đang cài **không có cả hai member này**. Các member gần nghĩa đang có:
   `SECTION_LABEL`, `SECTION_LABEL_TICKED`, `CAPTION`, `TABLE_HEADER`.
3. `git log -S "StyleRole.HEADING"` chỉ ra commit đưa vào là `8254df7`
   *"refactor(settings): apply BODY_LABEL/HEADING/CAPTION roles, scope two
   cascading sheets (**EPIC-007F**, 3/13)"* — 2026-08-25.

> ⚠️ Chưa xác minh: vì sao app dùng member mà Engine không có. Có mùi
> **drift 2 repo** (đúng loại bẫy `CLAUDE.md` §3 cảnh báo), nhưng đó mới là
> giả thuyết — chưa kiểm chứng, chưa xem lịch sử Engine, chưa loại trừ khả
> năng khác.

## Việc cần làm khi bắt tay sửa

Theo [`bug-fix-rule.md`](../../../.agents/rules/bug-fix-rule.md):

1. Truy root cause thật trước (đừng vá bằng cách đổi đại sang `SECTION_LABEL`
   — phải biết ý đồ thị giác gốc của EPIC-007F là gì).
2. Viết regression test **đỏ đúng lý do** trước khi sửa. Ở đây gần như đã có
   sẵn: `test_every_navigable_route_constructs[settings]` đang đỏ đúng lý do.
3. Kiểm cả `BODY_LABEL` ở dòng 308 — sửa mỗi dòng 233 sẽ chỉ đẩy lỗi xuống
   dòng dưới.
4. Rà xem còn file nào khác trong app dùng member `StyleRole` mà Engine
   không có hay không.
