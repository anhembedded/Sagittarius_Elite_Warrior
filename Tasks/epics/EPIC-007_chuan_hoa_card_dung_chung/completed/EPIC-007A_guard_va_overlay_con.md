# EPIC-007A — Engine: guard bắt được `QWidget`, và `ConfirmOverlay`/`PickerOverlay` tồn tại thật

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong — 2026-08-25

> Code + commit nằm ở repo **Engine** (`BUG-004` đã đóng ở bảng bug bên đó). File này chỉ giữ
> bằng chứng và những chỗ đã lệch khỏi đề bài — hai bảng task độc lập, `.agents/ONBOARDING.md` §8.

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

- ✅ `BUG-004` đã chuyển sang `completed/` ở bảng bug Engine, Overview cập nhật 3→2 Open,
  4→5 Fixed.
- ✅ Guard chạy trên `src/presentation/ui` **trước** khi Elite migrate — **21 finding**, vượt
  mức sàn ≥19. Output đầy đủ ở dưới.
- ✅ Gate xanh. `pwsh` **không có** trong môi trường Linux đã sửa bài này, nên gate được chạy
  bằng đúng 5 bước với đúng tham số `ci-local.ps1` truyền (đọc từ script, dòng 199–266), trên
  Python 3.12 — không có block `===CI_LOCAL_RESULT===` để dán vì nó do chính script in ra.

### Guard output — `find_bare_qt_base_widgets` trên `src/presentation/ui`

```text
21 bare Qt base subclass(es) found outside widgets/surface.py or widgets/overlay.py:
  components/base_card.py:4                          extends QFrame   | class BaseCard(QFrame):
  components/chart_card/cached_frame_interaction.py:110  extends QWidget  | class _CachedFrameOverlay(QWidget):
  components/critical_error_dialog.py:29             extends QDialog  | class CriticalErrorDialog(QDialog):
  screens/backtest/backtest_modals.py:779            extends QWidget  | class _BotParamFieldWidget(QWidget):
  screens/backtest/backtest_top_panel.py:57          extends QWidget  | class BackTestTopPanel(QWidget):
  screens/backtest/backtest_trade_logs_panel.py:79   extends QFrame   | class _TradeLogRowWidget(QFrame):
  screens/backtest/backtest_trade_logs_panel.py:289  extends QWidget  | class BackTestTradeLogsPanel(QWidget):
  screens/backtest/backtest_widgets.py:46            extends QFrame   | class MetricCardWidget(QFrame):
  screens/backtest/backtest_widgets.py:213           extends QWidget  | class DynamicTabBarWidget(QWidget):
  screens/dashboard/dev_board_panel.py:88            extends QWidget  | class DevBoardPanel(QWidget):
  screens/data_management/data_management_view.py:85 extends QFrame   | class _StatusRowWidget(QFrame):
  screens/data_management/data_management_widgets.py:55   extends QWidget  | class TimeRangeCardWidget(QWidget):
  screens/data_management/data_management_widgets.py:156  extends QWidget  | class LogPanelWidget(QWidget):
  screens/data_management/data_management_widgets.py:248  extends QWidget  | class AppProgressBarWidget(QWidget):
  screens/data_management/data_management_widgets.py:291  extends QDialog  | class SymbolPickerDialog(QDialog):
  screens/data_management/data_management_widgets.py:383  extends QDialog  | class ConfirmDialog(QDialog):
  screens/data_management/data_management_widgets.py:465  extends QFrame   | class _KLineRowWidget(QFrame):
  screens/data_management/data_management_widgets.py:547  extends QDialog  | class KLineInspectorDialog(QDialog):
  screens/data_management/data_management_widgets.py:848  extends QFrame   | class _GapRowWidget(QFrame):
  screens/data_management/data_management_widgets.py:913  extends QFrame   | class _CoverageSegmentWidget(QFrame):
  screens/data_management/data_management_widgets.py:934  extends QDialog  | class GapInspectorDialog(QDialog):

by base: {'QDialog': 5, 'QFrame': 7, 'QWidget': 9}
```

**9 widget `QWidget`, không phải 7.** §Yêu cầu 3 liệt kê 7 tên; đo thật ra thêm
`_CachedFrameOverlay` và `_BotParamFieldWidget`. Con số "12" cũ đúng là mức sàn như §2 phát
hiện #4 đã ngờ.

### Gate (Engine, Python 3.12)

```text
ruff check sagittarius_engine tests examples tools        RC=0   All checks passed!
ruff format --check (widgets/ + test của nó)              RC=0
mypy ... --ignore-missing-imports --follow-imports=skip   RC=0   no issues in 394 files
pytest tests/ examples/student_management/tests/ ...      RC=0   1004 passed, 8 skipped
                                                                 coverage 89.46%
pytest tests/test_architecture.py                         RC=0   8 passed
```

Log: `Sagittarius_Engine/logs/gate-final-081651.log`, đã grep `FAILED|ERROR|Traceback|SyntaxError`
→ 0 mỗi loại. Baseline trước khi sửa: 971 passed.

## Rủi ro — đã kiểm, **không xảy ra**

Đề bài lo thêm `QWidget` sẽ làm CI Engine đỏ vì `tools/audit_dashboard/` là QtWidgets thuần.
Đo thật: `tools/audit_dashboard/` **không có** `class X(QWidget)` nào; cả Engine chỉ có đúng
một, là `BaseView` — nay đã mang marker miễn trừ.

Quan trọng hơn: **không có gì chạy guard lên cây nguồn thật.** Cả hai guard chỉ được gọi qua
fixture `tmp_path` trong `test_guards.py`; không CI job nào, không script nào trỏ chúng vào
`sagittarius_engine/` hay vào Elite. Nới regex vì thế không thể làm CI đỏ. Đây cũng là một
việc còn thiếu cho `EPIC-007`: guard mạnh hơn vẫn vô dụng chừng nào chưa ai gọi nó — ứng viên
cho `007C` (task đó đã có "coverage guard" trong phạm vi).

## Đã lệch khỏi đề bài — 1 chỗ, có chủ ý

§Yêu cầu 3 viết: *"dùng lại đúng quy ước `token-exempt` marker mà `find_inline_stylesheets`
đang dùng, không phát minh cái mới"*. Đã dùng marker **riêng**, `# base-exempt: <lý do>`.

Lý do: `kit/rectangle_card_guard.py:67` đã gặp đúng tình huống này và chọn marker riêng
(`card-exempt`), với lập luận áp thẳng được vào đây — *"this axis (shape, not a literal value)
is distinct from `qml_literal_guard`'s `token-exempt`"*. Trục của guard này là **lớp cha**,
không phải giá trị màu. Dùng chung một marker nghĩa là một miễn trừ được duyệt cho guard này
sẽ đồng thời tàng hình trước guard kia. Có test khoá: `token-exempt` đặt trên dòng
`class X(QFrame)` **không** làm im guard base class.

Chặt hơn 2 marker cũ một điểm: **lý do là bắt buộc**. `# base-exempt:` bỏ trống không được
tính là miễn trừ. `token-exempt`/`card-exempt` chỉ kiểm tra marker có mặt, nên marker trống
làm im chúng; trục này mới nên không vướng tương thích ngược.
