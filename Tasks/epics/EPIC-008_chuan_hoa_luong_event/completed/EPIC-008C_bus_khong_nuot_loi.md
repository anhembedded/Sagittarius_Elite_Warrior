# EPIC-008C — Engine: bus không được nuốt lỗi, và không được làm ngập log

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong (2026-08-25)
**Phụ thuộc:** `008A`

---

## Vấn đề

`MemoryEventBus.emit()` bọc mỗi handler trong `try/except Exception` rồi chỉ log **nếu có
logger**. `Sagittarius_Elite_Warrior/src/main.py:40` dựng bus bằng `MemoryEventBus()` — **không
truyền logger**. Nên `self.logger is None` và mọi lỗi trong mọi handler biến mất tuyệt đối.

**Cạm bẫy phải tránh:** "truyền logger vào là xong" **là sai**. `emit()` cũng log **mọi** lần
phát ở mức `INFO` kèm nguyên payload. `MarketTickEvent` bắn theo từng tick websocket → đúng
kiểu log flood đã làm treo luồng UI ở `BUG-042`. Bật logger mà không tách hai việc này ra là
tái tạo lại một bug đã biết.

## Yêu cầu

1. **Tách hai mối quan tâm**:
   - *Lỗi handler* → `ERROR` + traceback đầy đủ. **Luôn luôn.**
   - *Log mọi lần phát* → hạ xuống `DEBUG`, hoặc bỏ hẳn. Không được ở `INFO`.
2. **`NullLogger` thay cho `if self.logger:`.** Engine đã có sẵn `utils/null_logger.py` — dùng
   nó làm mặc định của tham số `logger`. Sau task này, `MemoryEventBus()` không có logger vẫn
   không **im lặng** — nó chỉ không ghi ra đâu cả, và đó là lựa chọn tường minh của người dựng.
3. **Cân nhắc `ResilientEventBus` trước khi viết decorator mới.** Engine **đã có**
   `infrastructure/event_bus/resilient_event_bus.py` — một decorator của `IEventBus` với retry +
   dead-letter queue. Elite chưa dùng. Đánh giá: dùng lại, mở rộng, hay viết
   `LoggingEventBus` riêng — ghi kết luận và lý do vào file này. **Không** viết trùng lặp mà
   không nói vì sao (`code-rule.md` §2: tái sử dụng trước khi tạo mới).
4. `main.py` của Elite dựng bus có logger thật (task ở phía Elite, `008G`).

## Bằng chứng phải nộp

- Test: handler ném exception → log `ERROR` có traceback; và emit 1.000 sự kiện ở `INFO`
  **không** sinh 1.000 dòng log.
- Đo lại `BUG-042`: chạy stream một khoảng, đếm số dòng log/giây trước và sau.
- `pwsh ./scripts/ci-local.ps1` — block `===CI_LOCAL_RESULT===` + log.

---

## Xong 2026-08-25
**Trạng thái:** ✅ Xong. Sửa ở **repo Engine**, file này ghi tiến độ phía Elite.

### Sửa cơ chế, không sửa một chỗ

Khi mở ra đọc thì phát hiện **cùng một bộ 3 lỗi lặp ở cả 4 bus**, không riêng `MemoryEventBus`
mà bug được báo:

| Bus | log mọi emit ở INFO | lỗi handler không có traceback | `if self.logger:` nuốt im lặng |
| :--- | :---: | :---: | :---: |
| `MemoryEventBus` | ✅ | ✅ | ✅ |
| `AsyncioEventBus` | ✅ | ✅ | ✅ |
| `ThreadPoolEventBus` | ✅ | ✅ | ✅ |
| `ResilientEventBus` | ✅ | **tệ hơn — không log gì cả**, chỉ đẩy vào DLQ | ✅ |
| `IpcQueueEventBus` | — | ✅ (riêng `_dispatch`) | ✅ |

Sửa mỗi `MemoryEventBus` thì đúng là hot fix — 4 bus còn lại vẫn nuốt lỗi y nguyên. Nên tạo
`infrastructure/event_bus/handler_reporting.py` là **nơi duy nhất** định nghĩa "báo cáo chuyện
gì xảy ra với handler", và cả 5 bus gọi vào đó.

### Ba quyết định gốc rễ

1. **`NullLogger` là sai cho đường lỗi — đây là chỗ task file này viết sai và mình không làm
   theo.** Yêu cầu #2 ban đầu ghi "dùng `NullLogger` thay `if self.logger:`". Nhưng `NullLogger`
   vứt hết mọi thứ, nên `MemoryEventBus()` không logger vẫn mất sạch exception — tức là **không
   sửa được đúng cái bug đã báo**, chỉ làm code đẹp hơn. Thay bằng
   `infrastructure/logging/fallback_logger.py` — forward sang `logging` chuẩn, **không cấu hình
   gì cả**. App đã cấu hình logging thì thấy record trong handler của mình; app chưa cấu hình gì
   vẫn thấy ERROR trên stderr nhờ `logging.lastResort` (level WARNING). Dù thế nào exception
   cũng để lại dấu vết.
   - Không dùng `StdLogger` làm fallback được: constructor của nó **xoá và thay handler** của
     logger `"App"` dùng chung và reset level — một thư viện âm thầm cấu hình lại logging của
     app chỉ vì không được truyền logger sẽ là bug nặng hơn cái đang sửa.
2. **Mức log là TRACE, không phải DEBUG.** `ILogger.trace` có docstring nói đúng trường hợp
   này: "quá dày kể cả cho một lần chạy `--dev` bình thường". `MarketTickEvent` bắn theo từng
   tick — đúng định nghĩa đó.
3. **Bỏ payload khỏi dòng log emit.** Hai lý do đo được: `ILogger` nhận `message: str` đã
   format sẵn nên **không có đường lazy-format** — `repr()` của payload vẫn chạy mỗi lần emit
   kể cả khi level đang tắt; và payload dump vào log là cách dữ liệu nghiệp vụ rò ra chỗ không
   ai định. Giữ tên event + số handler, đủ cho trace luồng.

### Dọn kèm phát sinh từ chính việc này

`ResilientEventBus.emit()` tự dựng lại `event_name`/`payload` **chỉ để viết dòng log của riêng
nó**, trong khi bus bên trong đã log rồi — một lần emit ra hai record nói cùng chuyện, và số
handler nó in ra là `len(self._wrapper_map)` (tổng wrapper của **mọi** event) chứ không phải
số handler của event đang emit. Bỏ hẳn dòng log đó: decorator này lo retry + DLQ, việc trace
thuộc về bus thực sự giữ handler. Test khoá lại bằng `assert logger.trace.call_count == 1`.

### Xác minh

- `tests/infrastructure/event_bus/test_handler_failure_reporting.py` — 11 test mới, parametrize
  qua từng bus. **Đỏ 9/11 trên code cũ** trước khi sửa (2 test isolation xanh sẵn, đúng — hành
  vi cô lập vốn đã đúng), xanh 11/11 sau khi sửa.
- `tests/infrastructure/` — 109 passed.
- Đúng invocation gate: **934 passed**, coverage 88.96%.
- `ruff check` / `ruff format` / `mypy` (đúng flag gate dùng) trên toàn cây: sạch.

### Hai bug mới phát hiện, đã file riêng thay vì sửa lẫn vào đây

- **`BUG-006`** — hai test "no QML runtime warnings" assert lên **toàn bộ** luồng message của
  Qt, nên một cảnh báo platform phát-một-lần-mỗi-tiến-trình (`QFontDatabase: Cannot find font
  directory`) rơi vào test nào là do **thứ tự collection** quyết định. Chứng minh dứt điểm:
  gallery chạy trước → gallery đỏ, roster xanh; roster chạy trước → **cả hai xanh**. Cùng code,
  kết quả ngược nhau. Đây cũng là lý do suite đi từ 1 lỗi lên 2 lỗi khi mình thêm file test mới
  — chỉ vì thứ tự đổi, không phải vì code hỏng.
  **Đính chính:** ở `008A`/`008B` mình đã báo lỗi này là "flaky/không đều". Sai — nó tất định,
  chỉ là phụ thuộc thứ tự.
- **`BUG-007`** — `ResilientEventBus.on()` key `_wrapper_map` bằng `__name__` trong khi cả
  package key bằng `event_name`/`__qualname__`; hai class event trùng `__name__` thì lần `on()`
  thứ hai **early-return im lặng**, handler không bao giờ chạy. Đã reproduce.

Cả hai **cố tình không sửa trong `008C`** — khác phạm vi, khác rủi ro; `BUG-007` đụng vào cách
resolve key nên có thể làm `off()` của consumer hiện tại không tìm thấy handler. Đúng
`design-discipline.md`: "thà để dở và gọi tên nó ra còn hơn làm xong mà sai".
