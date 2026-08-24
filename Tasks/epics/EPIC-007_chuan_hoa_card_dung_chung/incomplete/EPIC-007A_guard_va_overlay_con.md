# EPIC-007A — Engine: guard bắt được `QWidget`, và `ConfirmOverlay`/`PickerOverlay` tồn tại thật

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** 🔵 Chưa làm

---

## Phạm vi

Hai lỗ hổng ở `pyside_mvc/widgets/`, cả hai đều phải sửa **trước** khi Elite bắt đầu migrate —
nếu không, guard sẽ báo xanh cho đúng thứ nó cần bắt.

## Yêu cầu

1. **`Overlay` không được nhắc tới lớp không tồn tại.** `overlay.py:18` và thông báo `TypeError`
   ở dòng 33 đều bảo người dùng dựng `ConfirmOverlay` / `PickerOverlay`. Grep toàn engine:
   cả hai chỉ tồn tại dưới dạng `_ConfirmOverlay` cục bộ trong `tests/.../test_overlay.py`.
   → Đây là một **`BUG`** theo đúng luật BUG-vs-TASK của repo Engine (phát biểu sai sự thật về
   code). File `BUG-004` ở `Sagittarius_Engine/Tasks/bug_report/incomplete/` trước khi sửa.
2. **Hiện thực hai lớp đó thật**, mỗi lớp một file:
   - `widgets/overlays/confirm_overlay.py` — `ConfirmOverlay(Overlay)`: message + nút
     confirm/cancel + cờ `danger`. Consumer thật đang chờ: `ConfirmDialog` và
     `CriticalErrorDialog` của Elite (2).
   - `widgets/overlays/picker_overlay.py` — `PickerOverlay(Overlay)`: danh sách
     `SelectableCard` + ô tìm kiếm + `selected`. Consumer thật đang chờ: `SymbolPickerDialog`
     của DataMgmt + 6 picker của Backtest (7).
   - Cả hai đều thoả kỷ luật ≥2 instance thật; **không** tạo thêm lớp trung gian nào khác.
3. **Guard `find_bare_qt_base_widgets` phải bắt cả `QWidget`.** Regex hiện tại
   (`guards.py:_BARE_QT_BASE_RE`) chỉ khớp `QFrame|QDialog`, nên 7 widget của Elite kế thừa
   `QWidget` mà thực chất là surface có viền đều lọt: `LogPanelWidget`,
   `AppProgressBarWidget`, `TimeRangeCardWidget`, `DevBoardPanel`, `BackTestTopPanel`,
   `BackTestTradeLogsPanel`, `DynamicTabBarWidget`.
   - Thêm `QWidget` vào regex.
   - `QWidget` là lớp gốc hợp lệ cho những thứ **không** phải surface (ví dụ một composite
     thuần layout) → phải có cơ chế miễn trừ có ghi lý do, dùng lại đúng quy ước
     `token-exempt` marker mà `find_inline_stylesheets` đang dùng, không phát minh cái mới.
4. **Test hồi quy** cho cả 3 điểm trên.

## Bằng chứng phải nộp

- `BUG-004` ở bảng bug của Engine, có dòng ở `Overview`, chuyển sang `completed/` khi xong.
- Guard chạy trên `Sagittarius_Elite_Warrior/src/presentation/ui` **trước** khi Elite migrate,
  in ra ≥19 finding (12 cũ + ≥7 mới). Dán output vào file này.
- `pwsh ./scripts/ci-local.ps1` — dán nguyên block `===CI_LOCAL_RESULT===` và đường dẫn log.

## Rủi ro

Thêm `QWidget` vào guard sẽ làm CI của **Engine** đỏ nếu chính engine có `class X(QWidget)`
hợp lệ (`tools/audit_dashboard/` là PySide6 QtWidgets thuần). Kiểm tra trước khi bật, và dùng
cơ chế miễn trừ chứ không nới lỏng regex.
