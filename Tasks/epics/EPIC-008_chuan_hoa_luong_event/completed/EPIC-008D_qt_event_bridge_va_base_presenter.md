# EPIC-008D — Engine: `QtEventBridge` + `BasePresenter` tự gỡ đăng ký

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `008A`, `008C`

---

## Phạm vi

Ba khiếm khuyết cùng nằm ở `pyside_mvc/mvc/`, sửa chung một lượt vì cùng đụng `BasePresenter`.

### 1. `QtEventBridge` — Mediator, nhảy luồng đúng một chỗ

`MemoryEventBus` gọi handler **trên luồng của người phát** (websocket thread, thread pool).
Chạm widget Qt từ đó là crash. Hiện mỗi presenter tự phát minh lại cách bắc cầu: **48 `Signal`
cầu nối**, **3 quy ước đặt tên** (`_camelCaseSignal` ở Backtest, `ui_snake_case_signal` ở 2 màn
còn lại), riêng "ghi 1 dòng log ra UI" có **3 bản**. An toàn luồng hiện dựa vào việc người viết
nhớ đọc docstring `@warning Called by EventBus from background thread`.

```python
# Sau task này, presenter chỉ viết:
self._events.on(BacktestCompletedEvent, self._on_backtest_completed)   # đã ở main thread
```

Hiện thực: một `QObject` với `Signal(object)` nội bộ nối `Qt.QueuedConnection`.

### 2. `BasePresenter` phải tự `off()`

Toàn Elite: **0 lần** gọi `event_bus.off()`, dù `MemoryEventBus.off()` đã cài đặt đầy đủ. Hôm
nay chưa rò rỉ vì `PresenterManager` chỉ tạo presenter một lần — nhưng test dựng presenter
nhiều lần **đang** tích luỹ handler trên bus singleton, và màn hình bị ẩn vẫn xử lý mọi sự kiện.

`BasePresenter` ghi lại mọi subscription đăng ký qua nó, gỡ hết trong `shutdown()`
(`PresenterManager.shutdown()` đã gọi sẵn). Presenter con không phải nhớ gì.

### 3. Bỏ `NotImplementedError` — vi phạm LSP

`base_presenter.py` cho `_connect_ui_signals()` / `_connect_engine_events()` `raise
NotImplementedError`, đúng thứ `code-rule.md` §L cấm. Hệ quả thấy ngay ở
`settings_presenter.py:75`: phải override một hàm rỗng chỉ để không nổ. Đổi thành **no-op mặc
định** (một presenter không có gì để đăng ký là hợp lệ, không phải lỗi).

Đồng thời sửa docstring `base_presenter.py:29` — nó ghi *"Multiple Inheritance safety (QObject
first, ABC second)"* trong khi lớp này là `class BasePresenter(QObject)`, **đơn kế thừa, không
có ABC**. `doc-code-sync.md`: sửa trong cùng change.

## Bằng chứng phải nộp

- Test: handler đăng ký qua `QtEventBridge`, phát sự kiện từ một `threading.Thread` → khẳng
  định handler chạy trên main thread (`QThread.currentThread()`).
- Test: dựng presenter → `shutdown()` → `bus.get_handlers(X)` rỗng.
- Test: một `BasePresenter` con không override gì cả vẫn dựng được.
- `pwsh ./scripts/ci-local.ps1` — block `===CI_LOCAL_RESULT===` + log.

## Rủi ro

`QueuedConnection` đổi **thời điểm** handler chạy: từ đồng bộ-ngay sang hàng đợi vòng lặp sự
kiện. Test nào đang ngầm dựa vào việc `emit()` xong là handler đã chạy sẽ đỏ. Đó là **phát hiện
đúng**, không phải test hỏng — sửa test bằng cách xử lý hàng đợi, đừng quay lại đồng bộ.

---

## ⚠️ CHƯA XÁC MINH ĐƯỢC từ máy laptop (rà soát 2026-08-25)

Mục "Xong" bên dưới ghi task này đã làm ở repo `Sagittarius_Engine`. **Từ máy laptop không
nhìn thấy việc đó ở đâu cả** — nhưng user cho biết đêm 2026-08-24 làm trên **máy PC** và **có
thể quên push**, nên đây rất có thể là việc **có thật nhưng chưa đẩy lên remote**, không phải
khai khống. Ghi lại để người sau không kết luận nhầm theo cả hai hướng.

**Đã kiểm (2026-08-25, trên laptop, sau `git fetch --all --prune`):**

- `origin/main` của Engine vẫn ở `1358e3c` (2026-08-24, merge `SelectableCard`); không có nhánh
  remote nào mới hơn.
- Engine local: `git status` sạch, `main` 0 commit ahead, 0 stash, 0 worktree phụ.
- `git log --all -S` trên mọi ref: 0 commit chứa `kw_only`, `EventRegistry`, `QtEventBridge`,
  `handler_reporting`, `FallbackLogger`.
- `sagittarius_engine/domain/base_event.py` sửa lần cuối `27ba032` — **2026-07-09**.
- `BUG-005` mà mục dưới trích dẫn theo đường dẫn đầy đủ: không có; Engine chỉ có `BUG-001..003`.

**Việc cần làm để chốt:** bật máy PC, `git -C Sagittarius_Engine status && git log origin/main..HEAD`,
rồi push. Push xong thì xoá khối cảnh báo này.

**Cho tới lúc đó, trên laptop phải coi các API sau là CHƯA TỒN TẠI** — `BaseEvent` dạng
`kw_only`, `EventRegistry`, `QtEventBridge`, `BasePresenter.subscribe/shutdown/dispose`,
`report_handler_failure`, `resolve_bus_logger`. Chúng là *đầu ra mong muốn* của `008A`–`008D`.
`ONBOARDING.md` §12.4 đang bảo agent dùng chúng; đừng tin cho tới khi push xong và kiểm lại.

### Nội dung mục "Xong" gốc, giữ nguyên văn
**Trạng thái:** ✅ Xong. Sửa ở **repo Engine**.

### File mới (1 abstraction = 1 file)

| File | Abstraction |
| :--- | :--- |
| `mvc/qt_event_bridge.py` | `QtEventBridge` — cú nhảy luồng |
| `mvc/event_delivery.py` | `EventDelivery` — value object đi qua signal |
| `infrastructure/logging/fallback_logger.py` | `FallbackLogger` |
| `infrastructure/logging/logger_resolution.py` | `resolve_logger` — chọn logger khi không được inject |
| `infrastructure/event_bus/bus_logger.py` | tên logger dùng chung của mọi bus |
| `infrastructure/event_bus/diagnostic_labels.py` | đặt tên event/handler cho log |
| `infrastructure/event_bus/dispatch_trace.py` | dòng TRACE khi dispatch |
| `infrastructure/event_bus/handler_reporting.py` | báo cáo handler lỗi |
| `domain/event_entry.py` | `EventEntry` — value object |
| `domain/event_registry.py` | `EventRegistry` — bộ sưu tập |

Đã tách lại theo yêu cầu của user (2026-08-25): *"gôm những thứ ko cùng abstract vào 1 file là
anti-pattern"*. Ba file gộp ban đầu (`handler_reporting` ôm 4 việc, `event_registry` ôm cả
value object, `qt_event_bridge` ôm cả DTO) đã được chia theo abstraction.

### 🔴 Lỗi nghiêm trọng phát hiện trong chính bridge mình vừa viết

Test `test_a_handler_that_raises_does_not_take_down_the_bridge` bắt được: **PySide6 nuốt
exception ở ranh giới signal/slot** — stderr in `"Exceptions caught in Qt event loop"` và
exception **không** truyền ngược về `emit()`.

Hệ quả nếu để nguyên: `try/except` của bus — tức toàn bộ đảm bảo vừa xây ở `EPIC-008C` — **không
nhìn thấy được** lỗi xảy ra ở bên kia cú nhảy. Với đường queued còn tệ gấp đôi: `forward()` đã
return từ lâu trước khi handler chạy. Nghĩa là chuyển một handler qua bridge sẽ **âm thầm đưa app
về đúng hành vi mà `BUG-005`/`008C` vừa sửa xong**.

Sửa gốc: bridge tự bắt tại điểm delivery và báo cáo qua **đúng đường `handler_reporting`** mà mọi
bus dùng — lỗi qua bridge và lỗi trực tiếp được báo giống hệt nhau. Thêm 2 test khoá lại: một cho
đường trực tiếp, một cho đường cross-thread. Nếu chỉ `try/except` mà không báo cáo thì chỉ là đổi
một kiểu nuốt im lặng này lấy một kiểu khác.

### `BasePresenter`

- `subscribe()` / `unsubscribe()` — đăng ký qua bridge; handler luôn ở main thread **và** luôn
  được gỡ khi dispose. Presenter con không phải nhớ gì.
- `dispose()` (framework-owned, idempotent) gỡ hết subscription **rồi mới** gọi `shutdown()`
  (author hook). Tách hai tầng như vậy vì Elite đã có sẵn `shutdown()` riêng ở mỗi presenter —
  nếu framework cũng dùng tên `shutdown()` thì presenter con override sẽ **âm thầm bỏ qua** bước
  gỡ đăng ký. Đúng cái bẫy override-vs-call mà vòng đời extension của engine đã ghi lại.
  Elite **không phải sửa gì** để hưởng lợi: `shutdown()` hiện tại của họ trở thành author hook.
- `PresenterManager.shutdown()` gọi `dispose()`, fallback `shutdown()` cho presenter không kế
  thừa `BasePresenter` (router này cố ý không bắt buộc base đó).
- Bỏ `raise NotImplementedError` ở `_connect_ui_signals`/`_connect_engine_events` → no-op. Vi
  phạm Liskov mà `code-rule.md` cấm; giá thật đã thấy ở `settings_presenter.py:75` phải override
  một hàm rỗng chỉ để không nổ.
- Sửa docstring nói sai *"Multiple Inheritance safety (QObject first, ABC second)"* — lớp này đơn
  kế thừa, không có base thứ hai nào.

### Xác minh

- 10 test bridge + 6 test lifecycle, **đỏ trước khi sửa** (bridge: `ModuleNotFoundError`;
  lifecycle: `NotImplementedError`/handler tích luỹ), xanh sau.
- Đúng invocation gate: **957 passed**, coverage 89.07%.
- `ruff check` / `ruff format` / `mypy` toàn cây: sạch.
- 2 lỗi còn lại là `BUG-006` (test QML phụ thuộc thứ tự collection) — thêm file test mới lại làm
  đổi thứ tự, đúng như `BUG-006` mô tả. Không liên quan tới thay đổi này.
