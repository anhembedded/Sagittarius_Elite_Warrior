# EPIC-008F — Elite: Shared Kernel + port trừu tượng cho mọi phụ thuộc engine

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
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
