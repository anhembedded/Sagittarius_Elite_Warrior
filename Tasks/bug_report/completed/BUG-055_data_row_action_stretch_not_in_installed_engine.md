# BUG-055 — Bảng Database vỡ: `DataRow` không nhận `action_stretch`

**Reported date:** 2026-08-26
**Severity:** Chưa đánh giá (nhưng mọi status row / gap row của màn Database **không dựng được**)
**Status:** ✅ Đã sửa 2026-08-26 — root-caused; **cùng một nguyên nhân với `BUG-054`**: Engine cài trong `.venv` là bản cũ
**Found by:** chạy regression sau khi merge `master-warrior` vào nhánh `EPIC-010` (không liên quan EPIC-010)

---

## Hiện tượng

```
File "src/presentation/ui/screens/data_management/data_management_view.py", line 158, in __init__
    super().__init__(
TypeError: DataRow.__init__() got an unexpected keyword argument 'action_stretch'
```

Ném ra lúc dựng `_StatusRowWidget`, tức là **ngay khi bảng có dòng đầu tiên**.

## Quan sát đã có (chưa phải root cause)

1. **Chữ ký thật của Engine đang cài** — không có `action_stretch`:
   ```
   DataRow.__init__(self, columns, *, actions=(), parent=None)
   ```
   (`sagittarius_engine/extensions/pyside_mvc/widgets/surfaces/data_row.py`)

2. **Có 2 call site truyền `action_stretch`**, không phải 1:
   - `data_management_view.py:161`
   - `data_management_widgets.py:569`

3. Cùng họ với [`BUG-054`](BUG-054_settings_screen_crashes_on_missing_stylerole_members.md):
   code app tham chiếu API Engine mà bản Engine đang cài không có. Có mùi
   **drift 2 repo** (đúng bẫy `CLAUDE.md` §3), nhưng **chưa kiểm chứng** —
   chưa xem lịch sử Engine, chưa loại trừ khả năng khác.

## Ảnh hưởng đo được

Chạy `tests/unit/presentation/ui/screens/test_data_management_presenter.py`
trên nhánh `feat/epic-010-ui-state-elite` ngay sau khi merge
`master-warrior`:

```
11 failed, 26 passed, 1 error
```

Con số **giống hệt** trước và sau khi thêm code `EPIC-010E` — đã đối chiếu
bằng `git stash`, nên đây là lỗi có sẵn của base, không phải hồi quy do
EPIC-010.

## Việc cần làm khi bắt tay sửa

1. Truy root cause trước: `action_stretch` là API Engine **sắp có** mà app đã
   dùng trước, hay là API **đã bị bỏ**? Hai hướng sửa ngược nhau hoàn toàn.
2. Sửa cả **2** call site — sửa mỗi `data_management_view.py` sẽ chỉ đẩy lỗi
   sang `data_management_widgets.py`.
3. Rà cùng lượt với `BUG-054`: nếu đúng là drift 2 repo thì nhiều khả năng
   còn API khác cũng lệch, nên soát một thể thay vì vá lẻ từng cái.

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
