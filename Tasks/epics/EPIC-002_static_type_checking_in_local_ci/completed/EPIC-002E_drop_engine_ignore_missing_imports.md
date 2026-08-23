# EPIC-002E — Gỡ `sagittarius_engine` khỏi `ignore_missing_imports`

**Trạng thái:** ✅ Hoàn thành (2026-08-23)
**Epic cha:** [EPIC-002 — Kiểm tra kiểu tĩnh (`mypy`) trong CI cục bộ](../README.md)
**Độ phức tạp:** 🟢 `S (Fast)`

---

## 1. Bối cảnh & vấn đề thật

`EPIC-002B` mở cổng `mypy` kèm một override trong `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
# python-binance and sagittarius_engine ship no type stubs / py.typed marker — ...
module = ["binance", "binance.*", "sagittarius_engine", "sagittarius_engine.*"]
ignore_missing_imports = true
```

Phần lý do viết cho `sagittarius_engine` **đã hết đúng**. Engine ship marker
PEP 561 (`sagittarius_engine/py.typed`) từ **2.2.0** (engine `TASK-027`), và
bản đang cài trong venv của app là **2.3.0** — kiểm chứng thật, không đọc tài
liệu:

```
pip show sagittarius-engine  → Version: 2.3.0
os.path.exists(<site-packages>/sagittarius_engine/py.typed) → True
```

Hậu quả của việc giữ override: theo PEP 561, `ignore_missing_imports` khiến
mypy **bỏ qua toàn bộ annotation có thật** của engine và hạ mọi symbol của nó
xuống `Any`. App import engine ở **61 file** trong `src/` + `scripts/` — tức
mọi lời gọi qua biên giới app↔engine đều nằm ngoài tầm kiểm tra, đúng lớp lỗi
mà `BUG-026` (nguồn gốc của cả epic này) đã gây ra. Override không còn là
"lấp một lỗ hổng của bên thứ ba" mà đã trở thành thứ **vô hiệu hoá chính cổng
mypy** ở đúng chỗ nó cần bảo vệ nhất.

`binance` (python-binance) thì **vẫn thật sự thiếu** stub/marker — phần
override cho nó giữ nguyên.

CHANGELOG của engine cho `2.2.0` nêu thẳng override này "can now be dropped",
kèm kết quả họ tự đo được: `Success: no issues found in 134 source files`.
Task này xác minh lại con số đó trên máy này với bản **2.3.0** thật, không
tin lời tài liệu.

## 2. Thiết kế & lý do

Tách override làm đúng một việc: **thu hẹp `module` list**, giữ nguyên
`ignore_missing_imports = true` cho riêng `binance`.

Không chọn phương án "thêm `sagittarius_engine` vào `exclude` của
`[tool.mypy]`" hay đặt override riêng với `follow_imports = "skip"`: cả hai
đều tiếp tục che kiểu của engine, chỉ là che bằng cú pháp khác. Mục tiêu là
**thấy** kiểu của engine, không phải đổi cách giấu nó.

Comment được viết lại để chỉ khẳng định điều đang đúng (`binance` thiếu
stub), cộng một đoạn ghi rõ **vì sao `sagittarius_engine` đã bị gỡ** và mốc
thời gian — để phiên sau không "khôi phục" lại override khi thấy engine trong
danh sách import của app.

## 3. Thay đổi theo từng file

| File | Thay đổi |
| :--- | :--- |
| `pyproject.toml` | `[[tool.mypy.overrides]]`: `module` từ `["binance", "binance.*", "sagittarius_engine", "sagittarius_engine.*"]` → `["binance", "binance.*"]`. Comment viết lại: bỏ khẳng định sai về engine, thêm ghi chú lý do gỡ (py.typed từ 2.2.0, cài 2.3.0) và hậu quả nếu giữ (mọi symbol engine thành `Any`). |

**Không có file `src/`/`scripts/` nào phải sửa** — xem §4.

## 4. Kiểm thử

**Bước 1 — chứng minh việc gỡ override có tác dụng thật.** Chỉ chạy mypy
"không lỗi" thì chưa phân biệt được "engine đã được phân tích" với "engine
vẫn bị bỏ qua". Dùng file probe cố tình gọi sai một symbol engine:

```python
from sagittarius_engine.interfaces.i_event_bus import IEventBus
def f(bus: IEventBus) -> None:
    bus.no_such_method_at_all()
```

→ `error: "IEventBus" has no attribute "no_such_method_at_all"  [attr-defined]`

Với override cũ, dòng đó là `Any` và im lặng. Đây là bằng chứng mypy đang đọc
interface thật của engine chứ không phải chỉ "không còn báo missing import".

**Bước 2 — cổng thật.** `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`,
đọc `LOG_FILE` đầy đủ rồi grep `FAILED`/`ERROR`/`Traceback` theo đúng
`ONBOARDING.md` §5 (bài học `BUG-029`/`BUG-030`), không tin console:

- `Mypy` — `Success: no issues found in 134 source files` ✅
  (trùng khớp con số engine CHANGELOG công bố, đo độc lập trên 2.3.0)
- `Ruff Lint` ✅ / `Ruff Format` ✅ / `Native Chart Build` ✅ /
  `Chart Benchmark Contract` ✅ / Tests + coverage gate ✅
- `RESULT: PASS`, `FAILED_STEPS: none`

## 5. Ghi chú Triển khai

- **Không có lỗi mới nào lộ ra** khi gỡ override — điều này *không* hiển
  nhiên trước khi chạy: CHANGELOG của engine cảnh báo rõ "expect your own
  type checker to surface new errors in your code after upgrading". Lý do
  app không dính: `src/presentation/` (nơi dùng engine dày nhất qua
  `pyside_mvc`) đang nằm trong `exclude` wholesale của `[tool.mypy]` từ
  `EPIC-002A`. Nghĩa là **kết quả sạch này chưa phải bằng chứng biên giới
  app↔engine đã hoàn toàn đúng kiểu** — nó chỉ đúng cho phần codebase hiện
  đang được gate. Khi `EPIC-002D` gỡ dần `presentation/` khỏi `exclude`,
  nhiều khả năng lớp lỗi engine↔app sẽ mới thật sự lộ ra ở đó.
- Đã grep toàn bộ `*.md` của repo tìm chỗ khác nhắc lại lý do sai
  (`py.typed`, `ignore_missing_imports`) — không có, `pyproject.toml` là nơi
  duy nhất chứa khẳng định này.
- Ghi nhận một chi tiết lệch trong `ci-local.ps1`: biến `$engineDir` trỏ tới
  `<repoRoot>/Sagittarius-Engine` (gạch nối) trong khi thư mục thật là
  `Sagittarius_Engine` (gạch dưới), nên `MYPYPATH` thực chất luôn chứa một
  đường dẫn không tồn tại. **Vô hại và không sửa trong task này**: engine
  được resolve từ site-packages (bản đã cài), đúng thứ cần kiểm tra kiểu —
  trỏ MYPYPATH vào cây nguồn engine mới là sai lệch so với cái app thật sự
  chạy. Ghi lại ở đây để phiên sau không nhầm đó là bug.
