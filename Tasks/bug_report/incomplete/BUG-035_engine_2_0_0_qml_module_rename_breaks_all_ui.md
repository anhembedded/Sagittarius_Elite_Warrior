# BUG-035 — Nâng engine lên 2.0.0 làm hỏng toàn bộ UI: `module "QmlShared" is not installed`

**Reported date:** 2026-08-23
**Severity:** Cao — toàn bộ UI không render, 69 test đỏ
**Status:** 🔴 Open — root cause đã xác định chính xác, chưa sửa (theo quy trình: phát hiện thì
lập task, không sửa tại phiên phát hiện)

---

## 1. Hiện tượng

Sau khi `pip install --upgrade sagittarius-engine` từ `1.5.0` lên `2.0.0`, chạy
`./scripts/ci-local.ps1 -Full`:

```
✅  Native Chart Build passed
✅  Chart Benchmark Contract passed
✅  Ruff Lint passed
✅  Ruff Format passed
✅  Mypy passed
❌  Tests FAILED
❌  Sanity FAILED
❌  Log Scan FAILED

================== 69 failed, 1702 passed, 2 errors in 38.65s ==================
```

Lint/format/mypy/native build/benchmark **đều xanh** — chỉ tầng UI vỡ.

Các lỗi lặp nhiều nhất trong log:

```
117  TypeError: Cannot read property 'textPrimary' of null
104  TypeError: Cannot read property 'border' of null
 65  TypeError: Cannot read property 'accent' of null
 44  AttributeError: 'NoneType' object has no attribute 'childItems'
 39  TypeError: Cannot read property 'muted' of null
```

## 2. Root cause

Dòng gốc, nằm trong Qt messages của test đầu tiên:

```
Sidebar.qml:4:1: module "QmlShared" is not installed
 import QmlShared 1.0
 ^
```

Engine `2.0.0` **đổi tên QML module** `QmlShared` → `Sagittarius.UI` và **không giữ tên cũ**.

Đối chiếu package-data hai bản:

| Bản | QML shipped |
| :--- | :--- |
| `1.5.0` | `extensions/pyside_mvc/QmlShared/*.qml` + `QmlShared/qmldir` |
| `2.0.0` | `extensions/pyside_mvc/Sagittarius/UI/<Component>/<Component>.qml` + `Sagittarius/UI/qmldir` |

Đổi tên xảy ra ở commit engine `a4a3bdb` — **sau** khi cắt `1.5.0`, nên `2.0.0` là lần đầu nó
tới tay consumer. Xem `CHANGELOG.md` của engine, mục 2.0.0.

Chuỗi nhân quả đầy đủ: QML import module không tồn tại → component không load → context
property `Theme` null → mọi `Theme.textPrimary`/`Theme.border`/... ném `TypeError` → item tree
rỗng → `walk_qml_items()` trong `tests/conftest.py:68` nhận `None` → `AttributeError`.
**Một nguyên nhân duy nhất, không phải 69 lỗi độc lập.**

## 3. Phạm vi

**26 file `.qml`** trong `src/` còn `import QmlShared 1.0`:

```bash
grep -rl "^import QmlShared 1.0" src/ --include="*.qml"
```

Phía Python **không bị ảnh hưởng** — đã kiểm 281 symbol engine mà app này import, chỉ 1 chỗ
hỏng và đó là [`BOT-118`](../../backlog/BOT-118_broken_state_tokens_import_in_test.md) đã biết
từ trước (`QmlShared.state_tokens`), không phải sinh ra bởi 2.0.0. Engine giữ
`QmlShared.log_list_model` làm shim tương thích có chủ đích cho chính app này.

## 4. Cách sửa

Đổi tên import, tên component giữ nguyên hoàn toàn:

```qml
import QmlShared 1.0        →  import Sagittarius.UI 1.0
```

`BaseCard`, `LogPanel`, `TimeRangeCard`, `StatefulButton`, `StyledCheck`, `FieldBackground`,
`DateTimePicker` — tên không đổi. 2.0.0 có thêm `AppDataTable` và `AppModal`.

### Yêu cầu

1. Đổi import trong cả 26 file. Cơ học, nhưng **đừng sed mù** — kiểm lại từng file có import
   nào khác cùng dòng không.
2. Gộp luôn `BOT-118` (`QmlShared.state_tokens` → `pyside_mvc.tokens.state_tokens`) và
   [`BOT-117`](../../backlog/BOT-117_stale_pyside_mvc_paths_in_palette_docstring.md) — cùng một
   gốc là đợt tái cấu trúc `pyside_mvc`, làm một thể thì rẻ hơn ba lần.
3. Chạy `./scripts/ci-local.ps1 -Full`, xác nhận về **1702+ passed, 0 failed** — nghĩa là
   đủ, không phải "ít lỗi hơn".
4. **Cân nhắc thêm một guard**: một test đọc `qmldir` mà engine thực sự ship rồi assert mọi
   `import <Module>` trong `src/**/*.qml` đều khớp. Cả lớp lỗi này hiện chỉ lộ ra lúc runtime,
   và chỉ khi test đó thực sự dựng được QML — chính là lý do 69 test đỏ cùng lúc thay vì 1 lỗi
   rõ ràng.

## 5. Ghi chú về quy trình

Bug này lộ ra **đúng như thiết kế**: nâng engine → chạy gate thật của app → đọc log. Nếu chỉ
chạy `pytest` lẻ hoặc tin vào việc "engine tests xanh" thì không thấy — engine tự test 746 case
đều xanh, vì engine dùng tên module mới của chính nó.

Engine's `CHANGELOG.md` bản đầu **thiếu** breaking change này; đã được sửa và ghi rõ lý do thiếu
(viết changelog từ trí nhớ commit gần nhất thay vì `git diff <tag>..HEAD`).

## 6. Phân loại

UI / QML / Engine integration
