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

---

## Root cause (2026-08-26)

**Không phải lỗi code app.** Repo Engine **có đủ** cả `StyleRole.HEADING`,
`StyleRole.BODY_LABEL` lẫn `DataRow(action_stretch=...)`. Bản Engine **đang cài
trong `.venv` là bản cũ hơn** — nên `BUG-054` và `BUG-055` **là cùng một lỗi**,
không phải hai.

Điều khiến nó khó thấy: **cả hai bản đều báo version `2.3.0`**. Engine đã đi
tiếp mà không bump version, nên số hiệu không phân biệt được. Đây đúng cái bẫy
[`install-rule.md`](../../../.agents/rules/install-rule.md) §1b đã ghi sẵn từ
`BUG-044`:

> *"the fixed engine still reports version `2.3.0`, the same number the broken
> build carried. An environment created before 2026-08-25 must reinstall rather
> than trust the version string."*

Thêm một chi tiết: bản đang cài đến từ **local path**
`file:///home/user/anhembedded/sagittarius_engine` (một checkout cũ), không phải
từ GitHub — tức là môi trường dùng Option 2 của `install-rule.md` trỏ vào cây
nguồn đã lỗi thời.

## Cách sửa

Không sửa dòng code app nào. Cài lại Engine theo `install-rule.md` Option 1:

```bash
uv pip install --python .venv/bin/python --reinstall --no-deps \
    git+https://github.com/anhembedded/Sagittarius_Engine.git
```

## Xác minh

| Trước | Sau |
| :--- | :--- |
| `test_data_management_presenter.py` + `tests/sanity/`: 11 failed, 1 error | **61 passed** |
| — | `tests/unit/`: **1802 passed**, 0 failed |
| — | `tests/integration/` + `tests/sanity/`: **104 passed**, 4 skipped |

Đã kiểm chữ ký thật sau khi cài lại:

```
DataRow.__init__(self, columns, *, actions=(), action_stretch=0, parent=None)
StyleRole.HEADING: True | StyleRole.BODY_LABEL: True
```

## Bài học ghi lại

Cả hai bug đều được báo là "code app tham chiếu API không tồn tại", và cả hai
đều **sai chẩn đoán ban đầu** theo cùng một kiểu. Khi một API "không tồn tại"
trong Engine, câu hỏi đầu tiên phải là *"bản đang cài có phải bản mới nhất
không?"* — trước khi kết luận app dùng sai. Version string ở đây **không** trả
lời được câu hỏi đó.
