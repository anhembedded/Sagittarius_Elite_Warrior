# EPIC-006A — Xoá QML đã chết (di sản của EPIC-005)

**Thuộc:** [`EPIC-006`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-24)

---

## Phạm vi

4 file `.qml` mà `EPIC-005D/E1/E2/E3` đã ngừng nạp nhưng cố tình giữ lại trên đĩa để rollback rẻ
(quy tắc của `EPIC-005`: "Không xoá file `.qml` ở commit migrate. Chỉ ngừng nạp nó."):

- `src/presentation/ui/screens/settings/SettingsScreen.qml` (363 dòng)
- `src/presentation/ui/screens/data_management/DatabaseScreen.qml` (993 dòng)
- `src/presentation/ui/screens/data_management/GapInspectorModal.qml` (328 dòng)
- `src/presentation/ui/screens/data_management/KLineInspectorModal.qml` (415 dòng)

`EPIC-005` đã kết thúc và merge vào `master-warrior` — rollback không còn cần nữa, dọn dồn vào
một commit riêng như README của `EPIC-005` đã nói trước.

## Phát hiện trước khi xoá: 1 test standalone còn tham chiếu file thật

`git grep` cho từng tên file phát hiện `tests/unit/presentation/ui/screens/
test_kline_inspector_modal_qml.py` — test guard `BUG-028` (column width scope trong QML) —
**vẫn đang load `KLineInspectorModal.qml` trực tiếp** qua `QQmlComponent`, độc lập với đường
chạy production (`EPIC-005E2` đã ngừng nạp file này qua `DataManagementView`, nhưng test đứng
riêng này không bị đó chạm tới nên vẫn pass bình thường). Xác nhận đang pass thật trước khi
động vào, không suy đoán.

Bug `BUG-028` (property khai báo sai scope trong QML) **không thể xảy ra nữa** khi không còn
file QML nào để có scope — xoá file thì xoá luôn test guard nó, không để nó gãy trong im lặng.

## Thay đổi

Xoá cả 5 file (4 `.qml` + 1 test). Không sửa gì khác.

## Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`. Baseline `1800 passed / 54
sanity` → `1799 passed / 54 sanity`: đúng -1, khớp chính xác 1 test bị xoá, không có gì lệch
ngoài dự kiến.
