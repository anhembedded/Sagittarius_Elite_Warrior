# EPIC-008F — Elite: Shared Kernel + port trừu tượng cho mọi phụ thuộc engine

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** ✅ Xong (2026-08-25)
**Phụ thuộc:** `008A`

---

## Phạm vi

User chốt hai điều tưởng như mâu thuẫn, task này là chỗ hoà giải chúng **tường minh**:

- *"Mọi thứ cần engine phải import qua port, phải có Abstract hẳn hoi."*
- *"Event phải kế thừa `BaseEvent`"* — mà `BaseEvent` là lớp cụ thể của engine, nằm ngay trong
  `domain/events/`.

**Cách hoà giải (user duyệt): Shared Kernel.** `IDomainEvent` + `BaseEvent` là một vùng dùng
chung **có tên, được ghi thành luật**, đúng 2 ký hiệu, không hơn. Mọi thứ khác của engine phải
qua port.

## Yêu cầu

1. **Sửa `.agents/rules/code-rule.md` §5** — thêm mục Shared Kernel ghi rõ: đúng 2 ký hiệu
   `sagittarius_engine.domain.i_domain_event.IDomainEvent` và
   `sagittarius_engine.domain.base_event.BaseEvent` được phép xuất hiện ở `src/domain/` và
   `src/application/`; lý do (engine sắp có tool audit cần marker type chung); mọi thứ khác
   phải qua port. **Không** để luật nói một đằng code làm một nẻo (`design-discipline.md` §2:
   sửa luật là thay đổi có chủ đích, không phải hệ quả phụ).

2. **`abc.ABC`, không `Protocol`** — user chốt: cần type safe **và ràng buộc thật**. Kiểm
   chứng: `Protocol` không chặn gì khi lớp con thiếu method; `ABC` ném `TypeError` ngay lúc
   dựng. Trạng thái hiện tại của `src/application/ports/` là **3 ABC / 3 Protocol**:

   | Port | Hiện tại | Sau task |
   | :--- | :--- | :--- |
   | `IExchangeClient` | `ABC` | giữ nguyên |
   | `IMarketDataRepository` | `ABC` | giữ nguyên |
   | `ISymbolMarketMetadataCache` | `ABC` | giữ nguyên |
   | `ICommandHandler` | `Protocol` | → `ABC` |
   | `IQueryHandler` | `Protocol` | → `ABC` |
   | `ILiveStreamService` | `Protocol` | → `ABC` |

   **Rủi ro thấp hơn tưởng:** cả 17 handler + `BinanceWebsocketService` **đã** khai báo kế
   thừa port tường minh sẵn (Protocol là structural nên trước đây không bắt buộc, nhưng họ vẫn
   viết). Cú pháp generic PEP 695 hoạt động với ABC — đã kiểm chứng:
   `class ICommandHandler[TCommand, TResponse](ABC)` + `@abstractmethod` chặn đúng lớp thiếu
   method. `i_cqrs.py` còn khai báo `TypeVar` kiểu cũ **thừa** bên cạnh cú pháp PEP 695 — dọn luôn.

3. **Thêm `src/application/ports/i_event_publisher.py`** — `IEventPublisher(ABC)`, đúng **một**
   phương thức: `publish(event: IDomainEvent) -> None`. Chỉ chiều phát; chiều nghe (`on`/`off`)
   chỉ xảy ra ở tầng Presentation, nơi được phép biết engine.

4. **Adapter** `src/infrastructure/events/engine_event_publisher.py` bọc `IEventBus`. Đăng ký
   trong `binance_bot_module.py`.

5. **Đổi 8 file** use-case/service từ `IEventBus` sang `IEventPublisher`.

6. **Bỏ `from sagittarius_engine import App`** ở
   `application/event_handlers/market_data/market_tick_event_handler.py:6` — tầng Application
   đang cầm cả runtime engine. Đây là vi phạm nặng nhất trong nhóm và không ai bàn cãi.

7. **4 event `@dataclass` thuần** ở `src/domain/events/` (`MarketTickEvent`,
   `SignalGeneratedEvent`, `BacktestCompletedEvent`, `BacktestFailedEvent`) chuyển sang kế
   thừa `BaseEvent` — hợp lệ nhờ Shared Kernel ở §1, và cần cho registry ở `008B`.

## Bằng chứng phải nộp

- `grep -rn "sagittarius_engine" src/domain src/application` → chỉ còn đúng 2 ký hiệu Shared
  Kernel. Dán output.
- Chứng minh ràng buộc thật: tạm bỏ một `@abstractmethod` implementation → `TypeError` lúc
  dựng. Dán output (đây là cái `Protocol` không làm được, và là lý do đổi).
- `EVENT_CATALOG.md` (từ `008B`) hiện đủ 6 event của Elite với `event_id`/`occurred_on`.
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`.

## Rủi ro

Đổi `Protocol` → `ABC` có thể lộ ra một implementer đang thiếu method mà không ai biết (vì
Protocol không kiểm tra lúc chạy). Nếu xảy ra: đó là **phát hiện đúng**, phải sửa implementer,
**không** hạ port về `Protocol` cho qua chuyện.

## Xong 2026-08-25

**Trạng thái:** ✅ Xong. Gate **Elite `RESULT: PASS` (1708 passed)**, **Engine `RESULT: PASS`
(974 passed)**.

### Bằng chứng §1 — chỉ còn đúng 2 ký hiệu Shared Kernel

```
$ grep -rn "sagittarius_engine" src/domain src/application --include=*.py
src/domain/events/backtest_failed_event.py:3:    from ...domain.base_event import BaseEvent
src/domain/events/signal_generated_event.py:3:  from ...domain.base_event import BaseEvent
src/domain/events/market_tick_event.py:3:       from ...domain.base_event import BaseEvent
src/domain/events/backtest_completed_event.py:3:from ...domain.base_event import BaseEvent
src/application/events/bulk_sync_events.py:3:   from ...domain.base_event import BaseEvent
src/application/events/sync_events.py:3:        from ...domain.base_event import BaseEvent
src/application/ports/i_event_publisher.py:25:  from ...domain.i_domain_event import IDomainEvent
```
(3 hit còn lại là chữ trong docstring, không phải `import`.) Luật này giờ **có test khoá**:
`test_indicator_script_conventions.py` đổi từ cấm cả `sagittarius_engine` sang **allow-list
đúng 2 đường dẫn module**, kèm 1 test riêng chặn việc nới allow-list thành prefix.

### Lệch với 7 yêu cầu — 3 chỗ, đều có lý do

1. **Thêm 2 port ngoài danh sách:** `IConfigReader` + `ICommandDispatcher`. Yêu cầu chỉ liệt kê
   `IEventBus`, nhưng `bulk_sync_market_data/handler.py` còn import `IConfig` và `IDispatcher` —
   không port chúng thì **tiêu chí nghiệm thu của chính task** ("chỉ còn 2 ký hiệu") không đạt.
   Mỗi cái chỉ 1 file dùng, 1 method → rẻ.
2. **Adapter đặt ở `infrastructure/engine_adapters/`**, không phải `infrastructure/events/` như
   task đề nghị. `engine_adapters/` đã chứa đúng loại object này (`live_stream_adapter.py`);
   tách thư mục theo *chủ đề* thay vì theo *tầng* là thứ `code-rule.md` §7 vừa cấm.
3. **Đổi tên tham số** `event_bus` → `event_publisher` (8 file src + ~14 file test). Để nguyên
   tên cũ mà đổi kiểu thành `IEventPublisher` sẽ đánh lừa người đọc sau.

### Hai hệ quả thật của việc kế thừa `BaseEvent` — user chốt phương án A

Gate bắt được, không phải tự khai:

1. **Mất `frozen=True`.** Python cấm dataclass frozen kế thừa non-frozen; `BaseEvent` không thể
   frozen vì nó cố ý hỗ trợ subclass `__init__` viết tay (`HealthUpdatedEvent`). Có **test thật**
   đang khoá tính bất biến (`FrozenInstanceError`) — tôi ban đầu khẳng định nhầm là "không ai
   dựa vào", đã đính chính. **User chốt A (2026-08-25):** chấp nhận mất, đổi test sang khoá
   hành vi mới + ghi rõ đánh đổi, để mất mát không bị giấu.
2. **`__eq__` bị phá** — `_event_id` là UUID/instance nên 2 event cùng payload **không** bằng
   nhau. Đây là **bug của `008A`**, không phải đánh đổi: sửa ở Engine bằng `compare=False` cho
   2 trường metadata, kèm test hồi quy. Equality quay về so theo payload, `event_id` vẫn duy nhất.

### Sót của tôi, gate bắt

`Protocol`→`ABC` **không** lộ implementer nào thiếu method (1661 passed, 0 `TypeError` abstract)
— rủi ro task nêu đã không xảy ra. Nhưng tôi grep thiếu `scripts/` và `tests/integration/`
(đúng bẫy #11 `ONBOARDING`), để lọt 1 script + 1 integration test còn truyền bus thô; mypy và
gate bắt được.
