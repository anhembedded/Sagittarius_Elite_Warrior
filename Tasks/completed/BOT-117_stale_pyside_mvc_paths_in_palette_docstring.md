# BOT-117: Sửa đường dẫn `QmlShared` cũ trong docstring của `palette.py`

## 1. Bối cảnh & vấn đề thật

Phát hiện 2026-08-23 khi đối chiếu thực hành xây dựng app mẫu bên
`Sagittarius_Engine` (`EPIC-002`) với cách app này đang thực sự dùng
`pyside_mvc` — quy trình mới: mỗi practice chốt xong ở app mẫu thì kiểm tra
chéo app này có theo đúng không, sai thì lập task ở đây để làm sau (không
sửa ngay tại phiên phát hiện).

`src/presentation/ui/assets/palette.py` có 2 dòng comment/docstring trỏ tới
đường dẫn cũ của `pyside_mvc`, đã đổi từ đợt tái cấu trúc 2026-08-23 bên
engine:

```
src/presentation/ui/assets/palette.py:10:
    theme bridge (sagittarius_engine.extensions.pyside_mvc.QmlShared,

src/presentation/ui/assets/palette.py:32:
    # State tokens (sagittarius_engine.extensions.pyside_mvc.QmlShared.state_tokens) —
```

Thực tế sau tái cấu trúc: `QmlShared/` giờ chỉ còn 1 file
(`log_list_model.py`, giữ lại làm compat shim có `DeprecationWarning`), toàn
bộ QML thật đã chuyển sang `Sagittarius/UI/` (theo component), còn
`state_tokens.py` đã chuyển vào `tokens/`. Hai dòng trên trỏ vào chỗ giờ đã
rỗng — không gây lỗi runtime (chỉ là comment/docstring), nhưng đánh lừa bất
kỳ ai (người hoặc AI session) đọc `palette.py` để hiểu theme bridge đang nằm
ở đâu.

## 2. Thiết kế + lý do

Sửa thuần comment, không đổi hành vi:
- Dòng 10: `sagittarius_engine.extensions.pyside_mvc.QmlShared` →
  `sagittarius_engine.extensions.pyside_mvc` (theo `import_boundary.py`,
  consumer chỉ được import từ top-level package, không phải path con —
  comment nên phản ánh đúng ranh giới import đó, không trỏ path con nào cả).
- Dòng 32: `QmlShared.state_tokens` → `tokens.state_tokens` (path thật sau
  khi engine tái cấu trúc).

Không cần task riêng để verify — đây là comment, `grep` xác nhận đủ.

## 3. Thay đổi theo từng file

- `src/presentation/ui/assets/palette.py` — sửa 2 dòng comment/docstring
  nêu trên.

## 4. Kiểm thử

Không cần test mới (không đổi hành vi runtime). Xác nhận bằng:
```bash
grep -n "QmlShared" src/presentation/ui/assets/palette.py
```
phải không còn kết quả nào sau khi sửa.

---

## ✅ Đã sửa — 2026-08-23

Đóng chung trong [`BUG-035`](../bug_report/completed/BUG-035_engine_2_0_0_qml_module_rename_breaks_all_ui.md)
— cùng gốc là đợt tái cấu trúc `pyside_mvc` của engine, làm một thể như task này đã đề xuất.
Chi tiết và bằng chứng verify nằm trong file đó. Gate `ci-local.ps1 -Full`: **PASS**, 1773 passed.
