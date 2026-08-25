# EPIC-008A — Engine: `BaseEvent` kế thừa được thật (`BUG-005`)

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong (2026-08-25)

---

## Vấn đề — chạy thật, không suy luận

```text
SingleSyncProgressEvent(symbol='BTCUSDT', interval='1m', current=1, total=10)
  MRO         : SingleSyncProgressEvent → BaseEvent → IDomainEvent → ABC → object
  event_name  : <KHÔNG CÓ>
  event_id    → AttributeError: no attribute '_event_id'
  occurred_on → AttributeError: no attribute '_occurred_on'
  to_dict()   → AttributeError
  bus key     : 'SingleSyncProgressEvent'   ← y hệt một @dataclass thuần
```

Nguyên nhân: `BaseEvent.__init__` mới là chỗ gán `_event_id`/`_occurred_on`, nhưng `@dataclass`
**sinh `__init__` riêng và không gọi `super().__init__()`**. Kết quả: kế thừa `BaseEvent` hiện
**không đem lại gì cả** — đúng 3/3 thành viên kế thừa đều hỏng.

→ Là **`BUG`** theo luật BUG-vs-TASK của Engine (code phát biểu sai về chính nó). File
`BUG-005` ở `Sagittarius_Engine/Tasks/bug_report/incomplete/` **trước** khi sửa, kèm log tái
hiện (`logging-rule.md`).

## Yêu cầu

1. `BaseEvent` thành `@dataclass`, hai trường metadata dùng `kw_only=True`:

   ```python
   @dataclass
   class BaseEvent(IDomainEvent):
       event_id: str = field(default_factory=lambda: str(uuid.uuid4()), kw_only=True)
       occurred_on: datetime = field(default_factory=lambda: datetime.now(UTC), kw_only=True)

       event_name: ClassVar[str]

       def __init_subclass__(cls, **kwargs) -> None:
           super().__init_subclass__(**kwargs)
           if "event_name" not in cls.__dict__:
               cls.event_name = cls.__qualname__
           EventRegistry.register(cls)      # thêm ở 008B
   ```

   **`kw_only=True` là bắt buộc.** Thiếu nó, lớp con `@dataclass` có trường không-mặc-định sẽ
   `TypeError: non-default argument follows default argument`. Đã dựng thử và xác nhận bản
   trên chạy đúng: lớp con vẫn truyền tham số vị trí được, `event_id`/`occurred_on` tự sinh,
   `event_name` mặc định `__qualname__` và ghi đè được.

2. **Không phá 3 consumer hiện có trong Engine**: `HealthUpdatedEvent` (`health_module.py:25`,
   có `event_name = "health.updated"` và `__init__` thủ công gọi `super().__init__()`),
   `SystemStateChangedEvent`, `TaskCompletedEvent` (`audit/events.py`). Cả 3 đều là lớp thường
   chứ không phải dataclass → phải chạy được cả hai kiểu.

3. `to_dict()` phải hoạt động cho cả lớp dataclass lẫn lớp thường.

4. **Elite**: bỏ `@dataclass` thừa hoặc giữ, nhưng `SingleSyncProgressEvent` /
   `BulkSyncProgressEvent` phải thật sự có `event_id`/`occurred_on` sau task này. 4 event
   `@dataclass` thuần trong `domain/events/` chuyển sang kế thừa `BaseEvent` ở `008F` (cần
   Shared Kernel chốt trước).

## Bằng chứng phải nộp

- Test hồi quy khẳng định đúng 3 dòng đang hỏng: `event_id`, `occurred_on`, `to_dict()` trên
  một lớp con `@dataclass`. Test phải **đỏ trên code hiện tại** trước khi sửa — dán cả hai lần chạy.
- `pwsh ./scripts/ci-local.ps1` — block `===CI_LOCAL_RESULT===` + đường dẫn log.

## Rủi ro

`BaseEvent` là API công khai của một thư viện **có người dùng ngoài Elite**
(`design-discipline.md`: "một shortcut ở đây sẽ ship và thành nợ vĩnh viễn trong codebase của
người khác"). Đổi từ `__init__` thủ công sang dataclass là thay đổi có thể phá tương thích —
nếu phá, đây là lý do chính đáng cho một release **major**, không phải patch (`release.md`).

---

## Xong 2026-08-25
**Trạng thái:** ✅ Xong. Sửa thực hiện ở **repo Engine** (`Sagittarius_Engine`, commit riêng —
xem `BUG-005`), file này chỉ ghi lại tiến độ phía Elite.

- `BUG-005` đã được file, sửa, và đóng ở
  `Sagittarius_Engine/Tasks/bug_report/completed/BUG-005_baseevent_inheritance_is_inert_for_dataclasses.md`.
- `BaseEvent` giờ là `@dataclass` với 2 trường metadata `kw_only=True`, backed bởi property cụ
  thể (không phải field public trùng tên với property abstract kế thừa — cách đó phá
  `abc.update_abstractmethods()` và làm mọi khởi tạo ném `TypeError`). `event_name` tự đặt qua
  `__init_subclass__`.
- Kiểm chứng cả 2 kiểu subclass: `@dataclass` có trường bắt buộc (kiểu
  `SingleSyncProgressEvent`/`BulkSyncProgressEvent` của Elite) và subclass `__init__` thủ công
  (kiểu `HealthUpdatedEvent` của Engine) — cả hai đều hoạt động đúng, có test.
- **Chưa đổi 4 event `@dataclass` thuần của Elite** (`MarketTickEvent`, `SignalGeneratedEvent`,
  `BacktestCompletedEvent`, `BacktestFailedEvent`) sang kế thừa `BaseEvent` — việc đó thuộc
  `EPIC-008F` (cần Shared Kernel đã chốt ở `code-rule.md`, chưa sửa file luật). Không làm trước
  vì `008F` là nơi sửa `code-rule.md` một cách có chủ đích, đúng `design-discipline.md` §2.

### Phát hiện phụ, không thuộc phạm vi `EPIC-008A` — báo lại theo `surprising-findings.md`

Chạy `pwsh ./scripts/ci-local.ps1` của Engine nhiều lần cho ra 2–4 test đỏ **không liên quan**
tới thay đổi này (kiểm chứng bằng `git stash`/`stash pop` qua 4 lần chạy — cùng lỗi xuất hiện
và biến mất bất kể có patch `BaseEvent` hay không):

1. `test_gallery_emits_no_qml_runtime_warnings` / `test_roster_screen_emits_no_qml_runtime_warnings`
   — môi trường thiếu font PySide6 (`QFontDatabase: Cannot find font directory`), không phải
   lỗi CardModel mà docstring của test đó mô tả.
2. `test_agents_docs_resolve.py` (2 case) — `FileNotFoundError` không đều khi test tự gọi
   `subprocess.run(["grep", ...])` bên trong gate chạy qua PowerShell; cùng loại vấn đề
   `TASK-034`/`TASK-028` của Engine đã ghi nhận.

Chạy đúng lệnh `pytest` mà gate dùng (không qua PowerShell wrapper) cho kết quả ổn định và khớp
baseline mọi lần: 1 lỗi font pre-existing, 911 passed, coverage 88.71%. Không file bug mới cho
việc này — cờ lại để người bảo trì Engine tự quyết.
