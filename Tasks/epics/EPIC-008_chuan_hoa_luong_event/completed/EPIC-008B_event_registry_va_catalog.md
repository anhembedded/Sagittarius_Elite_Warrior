# EPIC-008B — Engine: `EventRegistry` + `EVENT_CATALOG.md` sinh tự động

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong (2026-08-25)
**Phụ thuộc:** `008A`

---

## Vì sao không dùng enum, cũng không dùng tài liệu viết tay

Đã cân nhắc và loại cả hai (ADR §4.6):

| Phương án | Vì sao loại |
| :--- | :--- |
| Enum tập trung + map sang class | Tạo **nguồn sự thật thứ hai**; thêm event phải sửa 2 chỗ. Và **không chứa nổi 13 sự kiện của engine** — Elite không sở hữu chúng. |
| Tài liệu `.md` + luật "nhớ cập nhật" | Đúng kiểu hỏng mà `.agents/` của chính repo này đã dính: 16 file viết một lần rồi lệch suốt 3 tuần vì không có gì **bắt buộc** nó đi theo code. `doc-code-sync.md` sinh ra từ bài học đó. |

Chọn: **registry tự đăng ký + tài liệu sinh ra + test so khớp.** Không có bản sao viết tay ⇒
không có bước nào để quên.

## Yêu cầu

1. `EventRegistry` — file riêng, `sagittarius_engine/domain/event_registry.py`. Ghi lại:
   `event_name`, lớp, module, danh sách trường payload.
2. `BaseEvent.__init_subclass__` tự gọi `EventRegistry.register(cls)` (`008A`). Lập trình viên
   **không phải làm gì**.
3. **13 sự kiện chỉ có tên chuỗi** (`app.booted`, `extension.*`, `runtime.hosted.*`,
   `runtime.scheduler.*`, `runtime.tasks.*`, `UiActionFailedEvent`) đăng ký thủ công **một
   lần**, ngay cạnh chỗ chúng được phát — không gom vào một file danh sách riêng (đó lại là
   nguồn sự thật thứ hai).
4. Script `scripts/generate_event_catalog.py` sinh `EVENT_CATALOG.md`: tên, module, payload,
   ai phát, ai nghe.
5. **Test so khớp**: `EVENT_CATALOG.md` trong repo phải khớp với cái sinh ra từ registry —
   lệch thì CI đỏ. Dùng lại đúng cơ chế `tests/test_agents_docs_resolve.py`.
6. Guard: mọi lớp trong registry phải có **≥1 subscriber**, hoặc nằm trong danh sách
   "cố ý chưa nghe" **có ghi lý do**. Đây là thứ chặn tái diễn chuyện `UiActionFailedEvent`
   phát ra suốt mà không ai nghe.

## Bằng chứng phải nộp

- `EVENT_CATALOG.md` sinh ra, có đủ **21** sự kiện đã kiểm kê trong ADR §1.
- Test so khớp chạy thật: sửa tay 1 dòng trong `.md` → CI đỏ. Dán output.
- Guard "≥1 subscriber" chạy thật trên Elite: phải bắt được `UiActionFailedEvent` và
  `runtime.tasks.failed` **trước** khi `008G` sửa chúng.

## Ghi chú

Registry này chính là **nguồn dữ liệu cho tool audit** mà user dự định làm (event nào, callback
gì, chạy bao lâu). Thiết kế `register()` sao cho về sau gắn thêm được số đo thời gian chạy của
handler mà không phải đổi API — nhưng **không** hiện thực phần đo trong epic này.

---

## Xong 2026-08-25
**Trạng thái:** ✅ Xong. Sửa thực hiện ở **repo Engine**, file này ghi lại tiến độ phía Elite.

- `sagittarius_engine/domain/event_registry.py` — `EventRegistry` + `EventEntry`, export ở
  `domain/__init__.py`.
- `BaseEvent.__init_subclass__` (`008A`) gọi `EventRegistry.register(cls)` — mọi subclass tự
  đăng ký, không cần làm gì thêm.
- **13 sự kiện chỉ có tên chuỗi đã đăng ký thủ công đúng nơi định nghĩa**, đúng yêu cầu #3:
  4 sự kiện `extension.*` (`kernel/events.py`), 2 sự kiện `runtime.hosted.*`
  (`runtime/hosted/events.py`), 2 sự kiện `runtime.scheduler.*`
  (`runtime/scheduler/events.py`), 4 sự kiện `runtime.tasks.*` (`runtime/tasks/events.py`),
  và `"app.booted"` (`kernel/bootstrap.py`, không có class payload — payload là chính instance
  `App`).
- **Dọn kèm, cùng phạm vi:** trước đây các sự kiện này được `_emit()` bằng literal string
  (`"extension.initializing"`) trong khi dataclass đứng cạnh không hề có `event_name` — 2 nơi
  giữ cùng một hằng số mà không gì ràng buộc chúng khớp nhau. Đã thêm `event_name: ClassVar[str]`
  vào từng dataclass và sửa mọi call site dùng `<Class>.event_name` thay vì literal — một nguồn
  sự thật, đúng tinh thần `runtime/tasks/events.py`'s convention đã có sẵn trước đó.
- `scripts/generate_event_catalog.py` — sinh `EVENT_CATALOG.md` (16 dòng hiện tại) từ registry,
  tái dùng cách `tests/test_all_modules_importable.py` duyệt hết `sagittarius_engine/` để đảm
  bảo event ở extension ít dùng cũng được đăng ký.
- `tests/domain/test_event_catalog_matches_registry.py` — test so khớp, chạy generator trong
  **subprocess riêng** (không phải in-process) để tránh event giả do test khác định nghĩa ở
  module-scope làm nhiễu registry dùng chung của tiến trình.
- `tests/domain/test_event_registry.py` — 8 test case cho registry.

### Phát hiện thật trong lúc làm, tự bắt bằng chính test của mình (không phải downstream)

`EventEntry.payload_fields` ban đầu được tính **và lưu cứng** ngay trong `register()` — nhưng
`register()` chạy bên trong `__init_subclass__`, tức là **trước khi** `@dataclass` kịp trang
trí class (đã kiểm chứng bằng thực nghiệm ở `008A`: `__init_subclass__` là một phần của việc
tạo class, decorator chạy sau). Kết quả: mọi `BaseEvent` subclass dùng `@dataclass` sẽ có
`payload_fields == ()` vĩnh viễn trong catalog — sai nhưng **im lặng**, vì hiện tại chưa event
nào của engine là `@dataclass` (`HealthUpdatedEvent` và 2 event audit đều viết `__init__` tay).
Lỗi này sẽ lộ ra ngay khi `EPIC-008F` chuyển 4 event `@dataclass` của Elite sang kế thừa
`BaseEvent`, nếu không bắt trước. Bắt được nhờ chính test `test_dataclass_baseevent_subclass_registers_itself`
tự viết cho `008B` (không phải review, không phải downstream) — sửa gốc: `payload_fields`
chuyển thành `@property` đọc `dataclasses.fields()` **mỗi lần truy cập** thay vì snapshot đúng
một lần lúc đăng ký. `register_named()` (dùng cho 13 sự kiện chuỗi, gọi ở cuối module — class
đã decorate xong lúc đó) vốn không dính lỗi này, nhưng đổi thống nhất cả hai đường đăng ký
tránh hành vi khác nhau không ai nhìn ra được từ bên ngoài.

### Xác minh

- `tests/domain/` — 24 passed (12 test cũ/mới của `test_base_event.py`, 8 test registry mới,
  3 test catalog mới, 1 test tích hợp có sẵn).
- Đúng invocation của gate: `pytest tests/ examples/student_management/tests/ --cov=... 
  --cov-fail-under=80` → **923 passed**, coverage 88.85%, chỉ 1 lỗi pre-existing (font,
  không liên quan, đã xác minh ở `008A`).
- `ruff check`/`ruff format`/`mypy` (đúng flag gate dùng, `--ignore-missing-imports
  --follow-imports=skip`) trên toàn bộ `sagittarius_engine tests examples tools`: sạch.
- `pwsh ./scripts/ci-local.ps1`: cùng 4 lỗi flaky đã ghi nhận và điều tra kỹ ở `008A`
  (2 QML font-environment, 2 `grep` PATH-resolution không đều qua PowerShell) — không có lỗi
  mới, không lỗi nào liên quan tới registry/catalog.
