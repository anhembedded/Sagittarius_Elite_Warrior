# BUG-019 — `GapInspectorModal` không dựng được: `import Sagittarius.Theme` là module không tồn tại

**Reported:** 2026-08-20, phát hiện khi chạy full unit suite sau khi merge
nhánh `feat/BOT-112C-gap-visualizer-and-repair` (PR #73) vào `master-warrior`.
**Severity:** P1 — modal Gap Inspector là giao diện chính của `BOT-112C`, và
nó **không mở được trong app thật**, không chỉ hỏng trong test. Đồng thời làm
nhánh `master-warrior` đỏ.
**Status:** 🔴 **Open** — đã root-cause và xác minh, **chưa sửa** (theo yêu
cầu: chỉ lập hồ sơ).

## Symptom

`tests/unit/presentation/ui/test_preview_fixtures_exist.py::test_all_discovered_previews_build_cleanly`
fail:

```
AssertionError: QML errors in preview for 'data_management': [
  .../data_management/DatabaseScreen.qml:779:5: Type GapInspectorModal unavailable,
  .../data_management/GapInspectorModal.qml:4:1: module "Sagittarius.Theme" is not installed
]
```

Toàn suite: `1 failed, 1581 passed`.

## Root cause

`src/presentation/ui/screens/data_management/GapInspectorModal.qml` dòng 4:

```qml
import Sagittarius.Theme
```

**Module `Sagittarius.Theme` không tồn tại.** `Theme` trong dự án này là một
**context property**, không phải QML module: `register_theme()`
(`sagittarius_engine/extensions/pyside_mvc/QmlShared/theme_bridge.py:48-57`)
gọi `rootContext().setContextProperty("Theme", ...)`, và `QmlHostView` chạy
nó trước khi nạp bất kỳ QML nào — nên 18 chỗ dùng `Theme.*` trong file này
vốn đã hoạt động **mà không cần import gì cả**.

Import một module không tồn tại khiến QML engine không compile được cả
component, nên `DatabaseScreen.qml:779` không dựng nổi `GapInspectorModal`,
và `Connections.onOpenGapInspectorRequested` (dòng 785-789) sẽ không bao giờ
mở được modal trong app thật.

Grep toàn bộ cây UI xác nhận đây là **file duy nhất** dùng import này; mọi
QML khác (kể cả `SymbolPickerModal.qml` — modal cùng loại, dựng ngay cạnh
nó ở `DatabaseScreen.qml:774`) dùng `import QmlShared 1.0`.

## Vì sao CI không chặn được trước khi merge

Test duy nhất bắt được lỗi này là preview test (dựng QML thật và assert
`errors() == []`). Các test khác của `BOT-112C`
(`test_gap_inspector_presenter.py`) chỉ chạy tầng Python — presenter, query,
command — nên không chạm tới QML và pass sạch. Đúng ranh giới bốn tầng test
trong `.agents/rules/ci-rule.md` §6: test Unit của presenter không bao giờ
chứng minh được component QML dựng được.

## Suggested next steps (chưa thực hiện)

1. Xoá dòng `import Sagittarius.Theme`.
2. Kiểm tra `ModalDialogCard` (root element của file này) có resolve được
   không — nó nằm ở `src/presentation/ui/components/`, và `DatabaseScreen.qml`
   phải khai báo `import "../../components"` mới thấy. Rất có thể
   `GapInspectorModal.qml` cũng cần dòng import thư mục đó. **Chưa xác minh**
   — lỗi module chặn compile nên chưa quan sát được lỗi kế tiếp (nếu có).
3. Regression test: preview test hiện có đã đủ bắt lỗi này; xác nhận nó
   chuyển từ đỏ sang xanh, không cần viết test mới.
4. Cân nhắc bổ sung sanity/preview check cho mọi modal mới — hiện chỉ có
   preview của cả màn hình mới chạm tới chúng.
