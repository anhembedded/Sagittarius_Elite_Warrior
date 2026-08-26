# BUG-055 — Bảng Database vỡ: `DataRow` không nhận `action_stretch`

**Reported date:** 2026-08-26
**Severity:** Chưa đánh giá (nhưng mọi status row / gap row của màn Database **không dựng được**)
**Status:** 🔴 Mở — **chỉ ghi nhận hiện tượng, chưa điều tra root cause**
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
