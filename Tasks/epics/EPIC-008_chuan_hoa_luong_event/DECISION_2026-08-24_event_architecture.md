# ADR — Kiến trúc luồng sự kiện từ nền lên màn hình

**Thuộc:** [`EPIC-008`](README.md) — chuẩn hoá event, tách khỏi [`EPIC-007`](../EPIC-007_chuan_hoa_card_dung_chung/) (chuẩn hoá card) theo quyết định của user ngày 2026-08-24. README của epic chưa viết; ADR này ra trước.
**Ngày:** 2026-08-24
**Trạng thái:** 🟢 **Phần lớn đã chốt** — nhật ký quyết định ở §7. Còn **2 điểm** chờ user ở §4.9.

> ADR này tách khỏi ADR widget của `EPIC-006` vì đây là trục độc lập: có thể đúng kể cả khi
> ta không chuẩn hoá card nào, và ngược lại. Nó trả lời câu hỏi user nêu ra: *"các event đang
> rất lộn xộn, có những event phải được sub bởi nhiều màn hình"*.

**Đã chốt:** tách làm **2 epic** — `EPIC-007` card, `EPIC-008` event. Mỗi cái rollback độc lập.

---

## 1. DANH MỤC ĐẦY ĐỦ — mọi sự kiện chạy qua EventBus của ứng dụng này

Liệt kê **21** sự kiện, chia 3 nhóm theo nơi định nghĩa. Cột **"Sub"** = số **màn hình** đang
đăng ký; cột **"Sau epic"** là quyết định đã chốt ở §4.5.

### 1.1 Sự kiện do Elite tự định nghĩa (6)

| # | Sự kiện | Kiểu | Payload | Phát ra từ | Sub | Sau epic |
| :-: | :--- | :--- | :--- | :--- | :-: | :--- |
| 1 | `MarketTickEvent` | `@dataclass` thuần | `market_data` | `binance_websocket_service.py:157` — **mỗi tick websocket** | 1 · Dashboard | Giữ 1 màn |
| 2 | `SignalGeneratedEvent` | `@dataclass` thuần | tín hiệu chiến lược | `application/services/strategy_engine.py` | 1 · Backtest | Giữ 1 màn |
| 3 | `BacktestCompletedEvent` | `@dataclass` thuần | `result: BacktestResult` | `run_static_backtest/handler.py:184`<br>`run_realtime_backtest/handler.py:216` | 1 · Backtest | Giữ 1 màn |
| 4 | `BacktestFailedEvent` | `@dataclass` thuần | `reason: str` | `run_static_backtest/handler.py:108`<br>`run_realtime_backtest/handler.py:199` | 1 · Backtest | Giữ 1 màn |
| 5 | `SingleSyncProgressEvent` | `BaseEvent` (hỏng, xem §2.9) | `symbol, interval, current, total` | `sync_market_data/handler.py:60` | **2** · Backtest + DataMgmt | 2 màn qua **`SyncProgressFeed`** |
| 6 | `BulkSyncProgressEvent` | `BaseEvent` (hỏng, xem §2.9) | tiến độ sync hàng loạt | `bulk_sync_market_data/progress_reporter.py:47,60,73` | 1 · DataMgmt | Giữ 1 màn |

### 1.2 Sự kiện Engine **đang phát thật** mà Elite chưa dùng hết (3)

| # | Sự kiện | Phát ra từ | Sub | Vấn đề |
| :-: | :--- | :--- | :-: | :--- |
| 7 | `HealthUpdatedEvent`<br>(`"health.updated"`) | `HealthExtension.boot()` — **1 lần duy nhất, lúc boot** | 2 · Backtest + Dashboard | 🔴 **Cả 2 đăng ký đều là mã chết** — xem §2.1 |
| 8 | `UiActionFailedEvent` | `safe_ui_action` decorator, **mỗi lần một slot UI ném lỗi** | **0** | 🔴 Mọi lỗi UI đã bị bắt đều được phát ra dưới dạng sự kiện có cấu trúc (kèm traceback đầy đủ) — **và không ai nghe**. Xem §2.10 |
| 9 | `"runtime.tasks.failed"`<br>(`TaskFailed`) | `task_manager.py:126,187,214` — mỗi background task chết | **0** | 🔴 Elite dùng `ITaskManager` thật (websocket spawn task ở `binance_websocket_service.py:51`), nên sự kiện này **có phát**. Task nền chết là chuyện không màn nào biết. |

### 1.3 Sự kiện vòng đời Engine — có phát, chưa ai dùng (10)

| # | Tên chuỗi | Payload | Phát ra từ |
| :-: | :--- | :--- | :--- |
| 10 | `"app.booted"` | `context.app` | `kernel/bootstrap.py:79` |
| 11 | `"extension.initializing"` | `ExtensionInitializing(name)` | `extension_manager.py:165,243` |
| 12 | `"extension.started"` | `ExtensionStarted(name)` | `extension_manager.py:259` |
| 13 | `"extension.stopped"` | `ExtensionStopped(name)` | `extension_manager.py:334` |
| 14 | `"extension.disposed"` | `ExtensionDisposed(name)` | `extension_manager.py:315,341` |
| 15 | `"runtime.hosted.started"` | `HostedServiceStarted(name)` | `hosted_service_manager.py:47` |
| 16 | `"runtime.hosted.stopped"` | `HostedServiceStopped(name)` | `hosted_service_manager.py:64,81` |
| 17 | `"runtime.scheduler.started"` | `SchedulerStarted()` | `scheduler.py:92` |
| 18 | `"runtime.scheduler.stopped"` | `SchedulerStopped()` | `scheduler.py:108` |
| 19 | `"runtime.tasks.started"` | `TaskStarted(id, name)` | `task_manager.py:166` |

> Nhóm này **không phải việc phải làm** — liệt kê để bạn biết cái gì đang có sẵn. Chúng hữu
> ích nhất cho một màn "System Monitor" thật (Dev Board đang có sẵn khung log cho việc này).
> Lưu ý cả 10 cái đều định danh bằng **chuỗi**, ngược với quy ước D2 §5 — nếu dùng thì phải
> ghi ngoại lệ, vì đây là API của engine, Elite không đổi được.

### 1.4 Sự kiện tồn tại nhưng **không bao giờ được phát** trong Elite (2)

| # | Sự kiện | Lý do |
| :-: | :--- | :--- |
| 20 | `SystemStateChangedEvent` (audit) | Elite **không nạp** `AuditExtension` (`main.py:50-64` chỉ nạp DependencyValidator, AssetValidator, Logger, ThreadManager, BinanceBotModule, Health) |
| 21 | `TaskCompletedEvent` (audit) | như trên |

### 1.5 Phụ lục — tín hiệu Qt (không đi qua EventBus)

Không phải "event" theo nghĩa bus, nhưng cùng thuộc phạm vi lộn xộn, nên đếm luôn:

| Nơi | Số `Signal` | Ghi chú |
| :--- | ---: | :--- |
| `backtest_view_model.py` | **68** | god object, xem §6 |
| `data_management_view_model.py` | 30 | |
| `backtest_presenter.py` | 22 | quy ước `_camelCaseSignal` |
| `data_management_presenter.py` | 14 | quy ước `ui_snake_case_signal` |
| `dashboard_presenter.py` | 12 | quy ước `ui_snake_case_signal` |
| `dashboard_view_model.py` | 9 | |
| `settings_view_model.py` | 7 | |
| **Tổng** | **162** | trong đó **48** ở presenter, phần lớn chỉ để nhảy luồng |

---

## 2. Mười khiếm khuyết cụ thể (mỗi cái có bằng chứng)

### 2.1 🔴 Hai đăng ký `HealthUpdatedEvent` không bao giờ chạy được

`HealthExtension.boot()` phát sự kiện **đúng một lần**, ở bước 1 của `app_bootstrapper`
(`app_engine.boot()`). `MainWindow` mới được dựng ở bước 3, và `PresenterManager` là
**lazy** — presenter chỉ tồn tại khi user bấm vào màn hình đó lần đầu. Nghĩa là **tại thời
điểm sự kiện được phát, chưa có subscriber nào tồn tại**.

Hai dòng dưới đây là mã chết theo đúng nghĩa đen:

- `backtest_presenter.py:571` → `self.event_bus.on(HealthUpdatedEvent.event_name, ...)`
- `dashboard_presenter.py:427` → `self.event_bus.on(HealthUpdatedEvent.event_name, ...)`

Cả hai màn đã tự vá bằng cách **tự chế một sự kiện giả**: `_trigger_initial_health_check()`
(`backtest_presenter.py:574`, `dashboard_presenter.py:429`) resolve `HealthCheckQuery`, rồi
gọi thẳng handler với `HealthUpdatedEvent(status)` do chính nó dựng ra. Hai bản sao của cùng
một workaround, không bản nào ghi lại rằng subscription bên cạnh nó đã chết.

### 2.2 🔴 Mọi exception trong handler bị nuốt hoàn toàn, không dấu vết

`MemoryEventBus.emit()` bọc mỗi handler trong `try/except Exception` và chỉ log **nếu có
logger**. `src/main.py:40` dựng bus bằng `MemoryEventBus()` — **không truyền logger**. Nên
`self.logger` là `None`, và mọi lỗi trong bất kỳ handler nào của bất kỳ màn nào biến mất
tuyệt đối.

> ⚠️ Đừng sửa bằng cách "truyền logger vào là xong": `emit()` cũng log **mọi** sự kiện ở mức
> `INFO` kèm nguyên payload. `MarketTickEvent` bắn theo từng tick websocket → đó chính là
> kiểu log flood đã làm treo luồng UI ở `BUG-042`. Sửa chỗ này phải tách "log lỗi handler"
> khỏi "log mọi lần phát".

### 2.3 🟠 Cùng một bus, hai cách định danh sự kiện, trong cùng một file

`backtest_presenter.py` dòng 566–571 dùng **lớp** cho 4 sự kiện đầu và **chuỗi**
(`HealthUpdatedEvent.event_name`) cho sự kiện thứ 5. `MemoryEventBus._get_event_key()` chấp
nhận cả hai (`event_name` nếu có, không thì `__qualname__`), nên không ai bị lỗi — và cũng vì
thế không ai phát hiện ra sự bất nhất. Hệ quả thật: đổi tên lớp sẽ âm thầm làm hỏng
subscription của nhóm thứ nhất, còn đổi hằng `event_name` làm hỏng nhóm thứ hai.

### 2.4 🟠 Tầng Application import thẳng engine

`code-rule.md` §5: *"Never leak Infrastructure concerns (like `sagittarius_engine` base
classes...) into the Domain or Application layers"*. Thực tế:

- `application/events/sync_events.py:3`, `bulk_sync_events.py:3` → `from
  sagittarius_engine.domain.base_event import BaseEvent`
- `application/event_handlers/market_data/market_tick_event_handler.py:6` → `from
  sagittarius_engine import App` — import **cả engine** vào tầng Application
- 8 file use-case/service khác import `IEventBus` của engine

Xem Q2 §7 — ba dòng trên **không cùng mức độ sai**, và mình cố tình không gộp chúng làm một.

### 2.5 🟠 48 tín hiệu Qt tự chế chỉ để nhảy luồng, 3 quy ước đặt tên

`MemoryEventBus` gọi handler **trên luồng của người phát** (websocket thread, thread pool...).
Chạm widget Qt từ luồng đó là crash. Mỗi presenter tự phát minh lại cách bắc cầu về main
thread (bảng số liệu ở §1.5). Riêng "ghi một dòng log ra UI" có **3 bản**: `_uiLogSignal`
(Backtest), `ui_log_signal` (Dashboard), `ui_log_signal` + `ui_error_log_signal` (DataMgmt).
Không có cơ chế nào của engine đứng sau — chỉ có docstring cảnh báo (*"@warning Called by
EventBus from background thread"*), tức là an toàn luồng đang dựa vào việc người viết nhớ đọc
chú thích.

### 2.6 🟠 Payload là danh sách tham số vị trí, không phải kiểu dữ liệu

- `ui_status_table_signal = Signal(str, str, str, str, str, str)` — **6 chuỗi liên tiếp**
- `ui_gap_inspector_signal = Signal(str, str, int, int, float, list, list)` — 7 tham số
- `_backtestProgressSignal = Signal(int, str, int, int, float)`

`code-rule.md` §1 yêu cầu dùng `dataclasses` thay cấu trúc thô — 6 chuỗi vị trí còn tệ hơn
dict: hoán đổi nhầm 2 cột là lỗi thầm lặng, mypy không bắt được.

### 2.7 🟠 Có `on()` nhưng chưa từng có `off()`

Toàn repo: **0 lần** gọi `event_bus.off()`, dù `MemoryEventBus.off()` đã cài đặt đầy đủ.
Hôm nay chưa rò rỉ vì `PresenterManager` chỉ tạo presenter một lần. Nhưng: màn hình bị ẩn vẫn
xử lý **mọi** sự kiện ở nền; và test dựng presenter nhiều lần sẽ tích luỹ handler trên bus
singleton — handler của test trước vẫn chạy trong test sau.

### 2.8 🟠 `BasePresenter` vi phạm LSP và tự mô tả sai

`base_presenter.py:29` ghi *"Multiple Inheritance safety (QObject first, ABC second)"* —
lớp này là `class BasePresenter(QObject)`, **đơn kế thừa, không có ABC**. Và
`_connect_ui_signals()` / `_connect_engine_events()` `raise NotImplementedError`, đúng thứ
`code-rule.md` §L (Liskov) cấm — hệ quả thấy ngay ở `settings_presenter.py:75`, phải override
một hàm rỗng chỉ để không nổ.

### 2.9 🔴 Kế thừa `BaseEvent` **hiện không đem lại gì cả** — 3 thành viên kế thừa đều hỏng

Chạy thật, không suy luận:

```
MRO: SingleSyncProgressEvent → BaseEvent → IDomainEvent → ABC → object
event_name  : <KHÔNG CÓ>
event_id    → AttributeError: 'SingleSyncProgressEvent' object has no attribute '_event_id'
occurred_on → AttributeError: ... has no attribute '_occurred_on'
to_dict()   → AttributeError: ... has no attribute '_occurred_on'
bus key     : 'SingleSyncProgressEvent'   ← y hệt một @dataclass thuần
```

Nguyên nhân: `BaseEvent.__init__` mới là chỗ gán `_event_id`/`_occurred_on`, nhưng
`@dataclass` **sinh ra `__init__` riêng và không gọi `super().__init__()`**. Nên hai sự kiện
"có kế thừa" của Elite đang nhận được **đúng bằng không** so với một dataclass trần: cùng khoá
bus, và cả ba thành viên thừa kế đều ném `AttributeError` nếu ai đó chạm vào.

Đây là dữ kiện làm Q2 gần như tự trả lời — xem §7.

### 2.10 🔴 Hai luồng báo lỗi có cấu trúc đang chảy vào hư không

- `UiActionFailedEvent`: `safe_ui_action` bắt mọi exception trong slot UI, ghi log, rồi
  **phát ra một sự kiện có cấu trúc kèm traceback đầy đủ** — docstring của nó còn ghi rõ
  *"subscribe via `event_bus.on(UiActionFailedEvent, handler)`"*. Toàn Elite: **0 subscriber**.
- `"runtime.tasks.failed"` / `TaskFailed`: mỗi background task chết đều phát sự kiện này.
  Elite dùng `ITaskManager` thật (websocket spawn task ở `binance_websocket_service.py:51`).
  **0 subscriber.**

Cộng với §2.2 (bus nuốt exception, không logger), kết quả là: **một lỗi ở tầng nền có thể
xảy ra mà không để lại dấu vết ở bất kỳ đâu người dùng nhìn thấy được.**

---

## 3. Nguyên nhân gốc chung

Cả 10 khiếm khuyết đều là cùng một thứ: **EventBus của engine là một cơ chế trung lập, và
không có tầng nào ở giữa nó với Qt.** Nên mỗi màn hình phải tự trả lời lại từ đầu 5 câu hỏi
giống hệt nhau — nhảy luồng thế nào, định danh event ra sao, payload đóng gói kiểu gì, ai gỡ
đăng ký, sự kiện phát trước khi mình sinh ra thì sao — và ba màn hình đã trả lời khác nhau ở
cả 5 câu.

Đây **cùng một hình dạng vấn đề** với phần card: engine cung cấp nguyên liệu thô (`QFrame`,
`IEventBus`), Elite không có tầng chung, nên mỗi màn tự chế. Card thì lộ ra bằng mắt; event
thì không, nên nó tệ hơn mà lâu bị phát hiện hơn.

---

## 4. QUYẾT ĐỊNH — user chốt 2026-08-24

> Trạng thái các mục dưới đây: **Đã chốt**, trừ hai chỗ đánh dấu ⚠️ ở §4.1 và §4.9.

### 4.0 Nguyên tắc nền — trả lời trực tiếp câu "event phải được sub bởi nhiều màn hình"

**Một sự kiện có đúng MỘT nơi xử lý, nhiều nơi *hiển thị*.**

Đây là chỗ dễ đi sai nhất. "Nhiều màn hình cần biết về sự kiện X" **không** có nghĩa là mỗi
màn tự `event_bus.on(X, self._handle_x)`. Làm thế thì logic xử lý bị nhân bản đúng bằng số
màn hình — và đó chính xác là thứ đang xảy ra với `HealthUpdatedEvent` (3 bản định dạng khác
nhau cho cùng một dict) và `SingleSyncProgressEvent` (2 handler khác nhau).

Cách đúng: một **Feed** duy nhất đăng ký sự kiện, chuẩn hoá nó thành một view-model, rồi phát
lại cho bất kỳ màn nào muốn hiển thị. Số subscriber trên bus **không phải mục tiêu cần tăng**;
số nơi *hiển thị* mới là thứ được phép tăng.

```text
EventBus ──1 subscriber──► XxxFeed (chuẩn hoá 1 lần) ──► Dashboard hiển thị
                                                     ├─► Backtest hiển thị
                                                     └─► DataMgmt hiển thị
```

### 4.1 Sự kiện của Elite **phải** kế thừa `BaseEvent` của engine — và phải sửa cho nó chạy

**User chốt:** mọi event kế thừa `BaseEvent`, vì engine sắp có **tool audit** đọc được: có
những event nào, callback là gì, chạy bao lâu. Marker type chung là thứ tool đó cần.

Điều này **đảo ngược** đề xuất D8 ở bản ADR trước (bỏ `BaseEvent`) — ghi lại rõ ràng chứ
không sửa lặng lẽ. Đề xuất cũ dựa trên dữ kiện "`BaseEvent` hiện không đem lại gì" (§2.9),
nhưng đó là **lý do phải sửa nó**, không phải lý do bỏ nó.

**Sửa ở Engine** (repo khác, commit khác — đề xuất `BUG-005`): `BaseEvent` thành `@dataclass`
với 2 trường `kw_only`, cộng `__init_subclass__` tự đặt `event_name` và tự đăng ký vào
registry. Đã dựng thử và chạy đúng:

```python
@dataclass
class BaseEvent(IDomainEvent):
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()), kw_only=True)
    occurred_on: datetime = field(default_factory=lambda: datetime.now(UTC), kw_only=True)

    event_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if "event_name" not in cls.__dict__:
            cls.event_name = cls.__qualname__      # mặc định = tên lớp
        EventRegistry.register(cls)                 # Registry pattern — tự đăng ký
```

`kw_only=True` là mấu chốt: không có nó, lớp con `@dataclass` có trường không-mặc-định sẽ
`TypeError` vì "non-default argument follows default argument". Kiểm chứng thật:

```text
SingleSyncProgressEvent('BTCUSDT','1m',1,10)  → OK, vẫn truyền vị trí được
  event_id     = 8bcef082-...        (tự sinh)
  occurred_on  = UTC                  (tự sinh)
  event_name   = 'SingleSyncProgressEvent'
HealthUpdatedEvent(status={...})      → event_name = 'health.updated' (ghi đè được)
registry                              → ['SingleSyncProgressEvent', 'health.updated']
```

⚠️ **Mâu thuẫn cần bạn xử lý — xem §4.9.** Quyết định này và quyết định §4.2 ("mọi thứ của
engine phải qua port") **không thể cùng đúng nguyên văn**: `BaseEvent` là một lớp cụ thể của
engine, và nó phải nằm ngay trong `domain/events/` của Elite.

### 4.2 Mọi phụ thuộc vào engine ở tầng Domain/Application phải đi qua **port** của Elite

**User chốt:** *"mọi thứ cần engine phải import qua port, phải có Abstract hẳn hoi."*

Việc này **đã có tiền lệ sẵn trong chính repo**: `src/application/ports/` đang có 5 port
(`i_cqrs.py`, `i_exchange_client.py`, `i_live_stream_service.py`,
`i_market_data_repository.py`, `i_symbol_market_metadata_cache.py`), và `i_cqrs.py` ghi rõ
*"Replaces the engine's ICommand to maintain zero framework dependencies"*. `IEventBus` chỉ
đơn giản là port duy nhất chưa ai làm.

- Thêm `src/application/ports/i_event_publisher.py` — **chỉ chiều phát**:
  `publish(event: IDomainEvent) -> None`. Chiều nghe (`on`/`off`) chỉ xảy ra ở tầng
  Presentation, nơi được phép biết engine.
- Adapter ở `src/infrastructure/events/engine_event_publisher.py` bọc `IEventBus`.
- 8 file use-case/service đổi từ `IEventBus` sang `IEventPublisher`.
- `market_tick_event_handler.py:6` — bỏ `from sagittarius_engine import App`. Đây là cái sai
  nặng nhất trong cả nhóm và không ai bàn cãi.

**Kiểu abstraction:** dùng `typing.Protocol`, khớp với 5 port đang có. `code-rule.md` §2 cho
phép cả `abc.ABC` lẫn `Protocol`. Nếu bạn muốn `abc.ABC` thì phải đổi cả 5 port cũ cho nhất
quán — đó là một task riêng, không nên làm nửa vời. ⚠️ Xem §4.9.

### 4.3 `HealthCheckRequested` — bỏ hẳn cơ chế sticky

**User chốt Q4:** thêm event `HealthCheckRequested`.

Kéo theo một hệ quả tốt: **không cần sticky nữa**. Đề xuất D3 cũ (bus giữ lại giá trị cuối)
bị **loại bỏ** — cặp request/response giải quyết trọn vẹn mà không phải thêm khả năng mới nào
cho bus.

```text
Presenter mở màn ──publish──► HealthCheckRequested
                                      │
                          HealthExtension nghe, đo lại
                                      │
                                      └──emit──► HealthUpdatedEvent ──► HealthFeed ──► mọi màn
```

Được thêm: số liệu luôn **tươi tại thời điểm mở màn** (đúng như hôm nay), chứ không phải ảnh
chụp lúc boot. Hai bản `_trigger_initial_health_check()` bị xoá; hai dòng `event_bus.on(...)`
chết trở thành sống thật.

**Đây là một tính năng mới nhỏ ở Engine** (`HealthExtension` phải nghe request) — ghi rõ để
không ai tưởng là refactor thuần.

### 4.4 `UiActionFailedEvent` và `runtime.tasks.failed` phải có nơi nghe

**User chốt (Q3-B):** *"Cái này phải hoạt động trở lại."*

Một `SystemErrorFeed` (`presentation/ui/common/`), đăng ký **một lần** cho cả hai sự kiện,
đẩy vào `LogPanel` dùng chung của mọi màn. Đúng mẫu §4.0: một subscriber, nhiều nơi hiển thị.

Nhận xét của bạn — *"chắc do design kiểu gì mà khi AI code, design không hình dung được điều
đó"* — đúng nguyên nhân: `safe_ui_action` phát một sự kiện có cấu trúc và **giả định** sẽ có
người nghe, nhưng không có gì trong thiết kế bắt buộc điều đó. Cách chặn tái diễn: **guard**
ở §4.8 — mọi lớp trong registry phải có ≥1 subscriber, hoặc được liệt kê tường minh là
"cố ý chưa dùng".

### 4.5 Định tuyến sự kiện — các quyết định mình tự chốt theo best practice

Bạn uỷ quyền phần còn lại. Nguyên tắc mình áp dụng: **epic này là dọn dẹp, không phải thêm
tính năng.** Thêm một subscriber mới là thay đổi hành vi sản phẩm — nó thuộc về một task
tính năng riêng, có người quyết định nghiệp vụ, không lẫn vào một epic refactor mà
kill-criteria là "rollback được".

| Sự kiện | Quyết định | Lý do |
| :--- | :--- | :--- |
| `MarketTickEvent` | **Chỉ Dashboard.** Không đưa sang Backtest | User chốt. Và code xác nhận: `HISTORICAL_TICK` chỉ replay dữ liệu **lịch sử** ở độ phân giải tick — chính `backtest_fsm_matrix.py:83-86` ghi *"real-time bar tick (live trading, not backtest) are separate, not-yet-built modes"*. Tên `RunRealtimeBacktestCommand` là **tên gọi sai**, không phải tính năng live. Xem D9 |
| `BacktestCompletedEvent` / `BacktestFailedEvent` / `SignalGeneratedEvent` | Giữ 1 màn | Thêm subscriber = thêm tính năng, ngoài phạm vi |
| `BulkSyncProgressEvent` | Giữ 1 màn (DataMgmt) | như trên — ghi lại thành ứng viên cho task tính năng sau |
| `SingleSyncProgressEvent` | Giữ 2 màn, **nhưng qua 1 `SyncProgressFeed`** | Đang là 2 handler độc lập — đúng thứ §4.0 cấm |
| `HealthUpdatedEvent` | 2 màn qua `HealthFeed` | §4.3 |
| `UiActionFailedEvent`, `runtime.tasks.failed` | **`SystemErrorFeed`**, mọi màn hiển thị | §4.4 |
| 10 sự kiện vòng đời (§1.3) | Không đăng ký gì trong epic này | Nhưng **đưa vào registry** để tool audit tương lai nhìn thấy |
| 2 sự kiện Audit (§1.4) | Không làm gì | Elite không nạp `AuditExtension`; nạp nó là tính năng mới |

### 4.6 Sổ đăng ký sự kiện — **Registry tự đăng ký + tài liệu SINH RA, không viết tay**

Bạn hỏi: một tài liệu kèm guide "thêm event thì phải cập nhật", **hay** một file enum liệt kê
tất cả event rồi map sang class? **Mình khuyên: không chọn cái nào trong hai — chọn cái thứ ba.**

| Phương án | Vấn đề |
| :--- | :--- |
| **Enum tập trung + map sang class** | Tạo **nguồn sự thật thứ hai**. Thêm event phải sửa 2 chỗ; quên một chỗ thì lệch âm thầm. Nó cũng mâu thuẫn với D2 (định danh bằng lớp), và **không thể chứa 13 sự kiện của engine** — Elite không sở hữu chúng. |
| **Tài liệu .md + luật "nhớ cập nhật"** | Đúng **chính xác** kiểu hỏng mà `.agents/` của Engine đã dính: 16 file viết một lần rồi lệch suốt 3 tuần vì không có gì **bắt buộc** nó phải đi theo code. `doc-code-sync.md` sinh ra từ bài học đó. Một luật dựa vào trí nhớ con người thì sẽ hỏng, chỉ là chưa biết lúc nào. |
| ✅ **Registry tự đăng ký + tài liệu sinh ra + test so khớp** | Không có bản sao viết tay nào. Không thể quên, vì không có bước nào để quên. |

Cách làm:

1. `EventRegistry` ở engine. `BaseEvent.__init_subclass__` **tự** đăng ký (§4.1) — lập trình
   viên không phải làm gì cả. Đây là **Registry pattern**, và cũng chính là nguồn dữ liệu cho
   tool audit bạn định làm.
2. Sự kiện chỉ có tên chuỗi (13 cái của engine) đăng ký thủ công một lần trong engine, cùng
   chỗ chúng được phát.
3. Một script sinh `EVENT_CATALOG.md` từ registry: tên, module, payload, ai phát, ai nghe.
4. **Test so khớp**: file `.md` trong repo phải khớp với cái sinh ra từ code — lệch thì CI đỏ.
   Cùng cơ chế `tests/test_agents_docs_resolve.py` của Engine đang dùng.

**Guide cho người thêm event mới rút gọn còn đúng một câu:** *"Kế thừa `BaseEvent`, đặt file
riêng trong `domain/events/` hoặc `application/events/`, rồi chạy lại script sinh catalog."*
Không có bước "nhớ cập nhật tài liệu", vì không có tài liệu viết tay nào.

### 4.7 Các quyết định kỹ thuật còn lại

| ID | Quyết định | Design pattern |
| :--- | :--- | :--- |
| **D1** | `QtEventBridge` ở `pyside_mvc`: mọi handler đăng ký qua nó **luôn** chạy trên main thread. Xoá dần 48 signal cầu nối (không đụng signal ngữ nghĩa UI thật) | Mediator |
| **D2** | Luôn định danh sự kiện bằng **lớp**, không bằng chuỗi. Ngoại lệ có ghi chú: 13 sự kiện engine chỉ có tên chuỗi | — |
| **D4** | Payload của `Signal` là một `@dataclass(frozen=True)`; `Signal(object)` thay cho `Signal(str,str,str,str,str,str)` | Value Object |
| **D6** | `BasePresenter` ghi lại mọi subscription và tự `off()` trong `shutdown()`. Test: dựng → shutdown → `get_handlers()` rỗng | Scoped subscription |
| **D7** | Lỗi handler phải thấy được: bọc bus bằng **decorator** ghi log `ERROR` + traceback, tách khỏi dòng `INFO` log-mọi-lần-phát (`BUG-042`). `MemoryEventBus(logger=None)` dùng `NullLogger` (engine đã có sẵn `utils/null_logger.py`) thay vì `if self.logger:` | Decorator + Null Object |
| **D9** | Đổi tên `RunRealtimeBacktestCommand` → `RunHistoricalTickBacktestCommand`. Tên hiện tại nói dối về tính năng và đã suýt làm mình định tuyến sai `MarketTickEvent` | — |

> D7 có tiền lệ sẵn: engine đã có `ResilientEventBus` — một decorator của `IEventBus` với
> retry + dead-letter queue. Elite **chưa dùng**. Cân nhắc dùng luôn thay vì viết decorator mới.

### 4.8 Guard — luật phải máy kiểm được, không phải lời hứa

1. Cấm `event_bus.on("chuỗi")` và `on(X.event_name, ...)` trong `src/` (D2).
2. Cấm `sagittarius_engine` xuất hiện trong `src/domain/` và `src/application/`, **trừ**
   danh sách trắng ở §4.9 — theo đúng mẫu `import_boundary.SANCTIONED_DEEP_IMPORTS` mà
   Engine đã dùng cho việc y hệt.
3. Mọi lớp trong `EventRegistry` phải có ≥1 subscriber, hoặc nằm trong danh sách
   "cố ý chưa dùng" có ghi lý do (chặn tái diễn §2.10).
4. `EVENT_CATALOG.md` phải khớp với registry (§4.6).
5. Presenter không được khai báo `Signal` chỉ để nhảy luồng (D1) — đo bằng: không `Signal`
   nào được `emit()` từ trong một handler của event bus.

### 4.9 ⚠️ HAI THỨ CẦN BẠN XỬ LÝ TRƯỚC KHI VIẾT `README.md` CỦA EPIC

**(1) §4.1 và §4.2 mâu thuẫn trực tiếp với nhau.**

- §4.2 nói: *mọi thứ của engine dùng ở Domain/Application phải qua port trừu tượng của Elite.*
- §4.1 nói: *event của Elite phải kế thừa `BaseEvent` — một **lớp cụ thể của engine**, nằm
  ngay trong `src/domain/events/`.*

Không thể cùng đúng nguyên văn. Ba cách xử lý:

| | Cách | Hệ quả |
| :-: | :--- | :--- |
| **A** ⭐ | Tuyên bố `IDomainEvent` + `BaseEvent` là **Shared Kernel** — vùng nhỏ, có tên, được ghi vào `code-rule.md`, engine và app cùng sở hữu. Mọi thứ khác của engine vẫn phải qua port. Guard giữ danh sách trắng đúng 2 ký hiệu này. | Trung thực, có tên gọi trong DDD, và tool audit hoạt động. Phải sửa `code-rule.md` §5 để ghi ngoại lệ — **không** để luật nói một đằng code làm một nẻo. |
| **B** | Elite tự định nghĩa `BaseEvent` riêng | Giữ luật nguyên vẹn, **nhưng tool audit của engine không nhìn thấy event của Elite** — tức là hỏng đúng cái lý do bạn yêu cầu §4.1. |
| **C** | Bỏ luật "mọi thứ qua port", chỉ cấm import cụ thể (`App`, cài đặt cụ thể) | Ít việc nhất, nhưng đi ngược điều bạn vừa chốt ở Q2. |

**Mình đề xuất A.** Cần bạn xác nhận, vì nó sửa `code-rule.md` — mà theo
`design-discipline.md` §2, sửa luật phải là một thay đổi có chủ đích, không phải hệ quả phụ.

**(2) `Protocol` hay `abc.ABC` cho port mới?** Bạn nói *"phải có Abstract hẳn hoi"*. 5 port
đang có đều dùng `Protocol`. Mình đề xuất **`Protocol` cho nhất quán** (`code-rule.md` cho
phép cả hai). Nếu bạn muốn `abc.ABC` thật thì phải đổi cả 5 port cũ — một task riêng, không
làm nửa vời.

---

## 5. Phân rã file — đáp ứng yêu cầu "nhiều file nhất có thể"

Theo `code-rule.md` §S (*"Split by responsibility into separate files/modules"*) và §"No God
Objects", nhưng **có giới hạn** bởi §"Single-Scope Cohesion": những thứ thuộc cùng một vòng
đời phải ở chung một file (đúng như `*_fsm_matrix.py` đang làm).

| Đơn vị | Quy tắc file |
| :--- | :--- |
| Mỗi widget dùng chung ở engine | **1 file 1 lớp** (`log_panel.py`, `stat_card.py`, `data_row.py`, ...) |
| Mỗi `StyleRole` mới | ở chung `style.py` — **cùng vòng đời**, tách ra là vi phạm Single-Scope Cohesion |
| Mỗi sự kiện | **1 file 1 sự kiện** (`domain/events/` đang làm đúng) |
| Mỗi port | 1 file 1 port (`application/ports/` đang làm đúng) |
| Mỗi Feed | 1 file (`presentation/ui/common/<x>_feed.py`) |
| Payload dataclass của tín hiệu | `<screen>_signal_payloads.py`, cạnh presenter |

**Ngưỡng:** file > 400 dòng hoặc lớp > 15 phương thức công khai thì phải tách.

---

## 6. File đang vượt ngưỡng

| File | Dòng | Ghi chú |
| :--- | ---: | :--- |
| `backtest_presenter.py` | 2.652 | |
| `backtest_view_model.py` | 1.368 | **68 signal** |
| `backtest_modals.py` | 1.231 | 13 lớp |
| `data_management_widgets.py` | 1.156 | đã thành "thư viện chung" ngoài ý muốn |
| `data_management_view.py` | 818 | |
| `dashboard_presenter.py` | 801 | |

---

## 7. Nhật ký quyết định

| # | Câu hỏi | Chốt | Ngày |
| :-: | :--- | :--- | :--- |
| Q1 | Một epic hay hai? | **Hai** — `EPIC-007` card, `EPIC-008` event | 2026-08-24 |
| Q2 | Application import gì của engine? | **Mọi thứ qua port, có abstraction hẳn hoi** (§4.2) | 2026-08-24 |
| Q3-A | Bỏ hay giữ `BaseEvent`? | **Giữ và sửa cho chạy** — engine sắp có tool audit cần marker type (§4.1). Đảo ngược D8 cũ | 2026-08-24 |
| Q3-B | `UiActionFailedEvent`/`TaskFailed` | **Phải hoạt động trở lại** (§4.4) | 2026-08-24 |
| Q3-C | `MarketTickEvent` → Backtest? | **Không** — Backtest không có tính năng live (§4.5, xác nhận bằng code) | 2026-08-24 |
| Q3-D | Định tuyến các event còn lại | Uỷ quyền cho AI → **§4.5**, nguyên tắc "epic dọn dẹp, không thêm tính năng" | 2026-08-24 |
| Q4 | Sticky hay đo lại? | **Thêm `HealthCheckRequested`**, bỏ hẳn sticky (§4.3) | 2026-08-24 |
| Q5 | Enum hay tài liệu? | **Cả hai đều không** → Registry tự đăng ký + tài liệu sinh ra + test so khớp (§4.6) | 2026-08-24 |
| Q6 | Shared Kernel cho `BaseEvent`? | ⚠️ **CHƯA CHỐT** — §4.9 (1) | |
| Q7 | `Protocol` hay `abc.ABC`? | ⚠️ **CHƯA CHỐT** — §4.9 (2) | |

---

## 8. Ngoài phạm vi

- Đổi `MemoryEventBus` sang `ThreadPoolEventBus`/`AsyncioEventBus`: chưa có nhu cầu đo được;
  D1 giải quyết vấn đề luồng ở đúng chỗ cần giải quyết.
- Nạp `AuditExtension` để dùng 2 sự kiện ở §1.4: tính năng mới, không phải dọn dẹp.
- Thêm subscriber mới cho `BulkSyncProgressEvent` / `BacktestCompletedEvent`: ghi lại thành
  ứng viên tính năng, không làm trong epic dọn dẹp này (§4.5).
- Xây **tool audit** của engine: epic này chỉ dựng **registry** làm nền cho nó.
- Event sourcing / persistence sự kiện; IPC event bus (app này một tiến trình).
