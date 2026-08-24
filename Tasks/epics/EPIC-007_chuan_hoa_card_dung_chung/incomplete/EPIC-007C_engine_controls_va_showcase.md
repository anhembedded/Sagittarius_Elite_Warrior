# EPIC-007C — Engine: control lá + showcase + coverage guard

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `007B`

---

## Phạm vi

Ba control lá bị lặp nhiều nhất, cộng phần showcase mà `guards.py` **tự ghi nhận là còn
thiếu** (*"No coverage-guard counterpart yet ... no QtWidgets showcase/preview exists yet"*).

| Lớp mới | File | Kế thừa | Instance thật |
| :--- | :--- | :--- | ---: |
| `StyledLabel` (abstract) | `widgets/controls/styled_label.py` | `QLabel` | gốc của 2 lớp dưới |
| `SectionLabel` | `widgets/controls/section_label.py` | `StyledLabel` | 3 |
| `Badge` | `widgets/controls/badge.py` | `StyledLabel` | 4 |
| `StyledProgressBar` | `widgets/controls/styled_progress_bar.py` | `QProgressBar` | 2 |

## Yêu cầu

1. **Chuỗi kế thừa thứ 5 và thứ 6, vẫn đơn tuyến.** `QLabel → StyledLabel → {SectionLabel,
   Badge}` và `QProgressBar → StyledProgressBar`. Không đa kế thừa ở đâu — ràng buộc
   PySide6/Shiboken của ADR `EPIC-006` §3 giữ nguyên.
2. `StyledLabel` chỉ được tạo vì **có sẵn 2 lớp con thật ngay lập tức**. Nếu trong lúc làm phát
   hiện `Badge` và `SectionLabel` không dùng chung gì thật → bỏ `StyledLabel`, cho mỗi cái kế
   thừa thẳng `QLabel`. Đừng giữ một tầng trung gian rỗng.
3. **`SectionLabel` vẽ dấu tick accent bằng `border-left` trong QSS**, không tạo widget con —
   bản hiện tại của Elite (`dev_board_panel._SectionLabel`) là một `QHBoxLayout` chứa một
   `QFrame` 3×12px. Nếu QSS không cho kết quả thị giác tương đương thì ghi lại và giữ cách cũ;
   **không** im lặng chấp nhận khác biệt.
4. **Showcase**: một app QtWidgets nhỏ ở `tools/widget_showcase/` dựng mọi type trong
   `widgets/`. Đây là thứ thay `kit/gallery_coverage_guard.py` (nhắm QML, sẽ mất referent).
5. **Coverage guard**: test fail nếu có type nào trong `widgets/__all__` không xuất hiện trong
   showcase.

## Bằng chứng phải nộp

- Ảnh chụp showcase (hoặc `--screenshot` output) đính kèm.
- `pwsh ./scripts/ci-local.ps1` — block `===CI_LOCAL_RESULT===` + log.
- Coverage guard chạy thật: xoá tạm 1 type khỏi showcase → test phải đỏ. Dán output.
