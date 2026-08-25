# EPIC-008G — Elite: 3 Feed dùng chung + quy tắc đặt chỗ event

> **§2 đã được viết lại 2026-08-25 (user duyệt).** Tiêu đề cũ là *"xoá 48 signal cầu nối"* —
> chỉ tiêu đó **sai** và đã bị bỏ. Đo thật: 47/48 signal là cầu nối **thread**, không phải cầu
> nối **bus-handler**, nên `QtEventBridge` không thay thế được và xoá chúng là đẩy cập nhật UI
> sang worker thread. Xem khối "⛔ DỪNG" cuối file để biết số liệu và bằng chứng.
>
> Thay bằng **quy tắc đặt chỗ**, đã ghi thành luật ở
> [`architecture-rule.md` §6](../../../.agents/rules/architecture-rule.md) và **nhắc lại ngay
> trong code** ở khối khai báo signal của cả 3 presenter:
>
> - Sự thật **riêng của một màn** → Qt signal nội bộ (thread-hop là tính năng, không phải nợ).
> - Sự thật **hệ thống**, hoặc ≥2 màn cần → Event Bus + đúng **một** Feed chuẩn hoá.
> - **Thăng cấp khi consumer thứ hai xuất hiện thật**, không thăng trước.
>
> **Không đặt chỉ tiêu theo số đếm signal.** Sai ranh giới thì con số chỉ dẫn tới phá code đúng.

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** ✅ Xong (2026-08-25) — §1/§3/§4 xong, §2 dừng có lý do
**Phụ thuộc:** `008C`, `008D`, `008E`, `008F`

---

## Phạm vi

Đây là task hiện thực nguyên tắc nền của epic: **một sự kiện có đúng MỘT nơi xử lý, nhiều nơi
hiển thị.**

### 1. Ba Feed, mỗi cái một file trong `presentation/ui/common/`

| Feed | Nghe | Ai hiển thị | Thay cho |
| :--- | :--- | :--- | :--- |
| `SystemErrorFeed` | `UiActionFailedEvent`, `runtime.tasks.failed` | mọi màn | **không ai** — hiện 0 subscriber, lỗi chảy vào hư không |
| `HealthFeed` | `HealthUpdatedEvent` | Backtest + Dashboard | 2 bản `_trigger_initial_health_check()` + 3 bản định dạng |
| `SyncProgressFeed` | `SingleSyncProgressEvent` | Backtest + DataMgmt | 2 handler độc lập |

`SystemErrorFeed` là thứ user yêu cầu *"phải hoạt động trở lại"*. `safe_ui_action` phát một sự
kiện có cấu trúc kèm traceback đầy đủ và docstring của nó còn ghi rõ *"subscribe via
`event_bus.on(UiActionFailedEvent, handler)`"* — nhưng không có gì trong thiết kế **bắt buộc**
điều đó, nên chưa ai làm. Guard ở `008H` là thứ chặn tái diễn.

### 2. Xoá 48 signal cầu nối

| Presenter | Số `Signal` | Quy ước |
| :--- | ---: | :--- |
| `backtest_presenter.py` | 22 | `_camelCaseSignal` |
| `data_management_presenter.py` | 14 | `ui_snake_case_signal` |
| `dashboard_presenter.py` | 12 | `ui_snake_case_signal` |

Handler đăng ký qua `QtEventBridge` (`008D`) đã ở main thread ⇒ cầu nối không còn lý do tồn tại.

**Ranh giới phải giữ:** chỉ xoá signal **cầu nối luồng**. Signal mang **ngữ nghĩa UI thật**
(`view_model → view`) giữ nguyên — hai loại này đang bị trộn lẫn, tách chúng ra là một phần
việc của task này. Tiêu chí phân biệt: một signal chỉ tồn tại để chuyển luồng thì nơi
`emit()` nó là một handler của event bus (hoặc một callback worker), và slot nhận không làm gì
ngoài chuyển tiếp.

### 3. Payload thành dataclass

| Hiện tại | Sau |
| :--- | :--- |
| `ui_status_table_signal = Signal(str, str, str, str, str, str)` | `Signal(object)` mang `StatusRowUpdate` |
| `ui_gap_inspector_signal = Signal(str, str, int, int, float, list, list)` | `Signal(object)` mang `GapInspectorPayload` |
| `_backtestProgressSignal = Signal(int, str, int, int, float)` | `Signal(object)` mang `BacktestProgress` |

Đặt ở `<screen>_signal_payloads.py` cạnh presenter. `@dataclass(frozen=True)`. `code-rule.md`
§1 yêu cầu dataclass thay cấu trúc thô — 6 chuỗi vị trí còn tệ hơn dict: hoán nhầm 2 cột là lỗi
thầm lặng mà mypy không bắt được.

### 4. `main.py` dựng bus có logger thật

Sau `008C`, `MemoryEventBus` nhận logger tường minh thay vì `None`.

## Bằng chứng phải nộp

- Đếm `Signal` trong 3 presenter trước/sau. Với **mỗi** signal bị xoá, một dòng nói nó là cầu
  nối luồng (không phải ngữ nghĩa UI).
- Test: gây một lỗi trong slot UI → `SystemErrorFeed` nhận được và log panel hiện ra. Đây là
  bằng chứng cho yêu cầu "phải hoạt động trở lại".
- Log 2 màn cho thấy chuỗi health giống hệt nhau, và `grep _trigger_initial_health_check` → rỗng.
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`.

## Rủi ro

Đây là task lớn nhất epic và đụng vào cả 3 presenter cùng lúc. **Chia commit theo presenter**,
không gộp. Nếu số signal xoá được ít hơn hẳn dự kiến (ví dụ < 30/48), dừng lại và ghi lý do —
nhiều khả năng ranh giới "cầu nối vs ngữ nghĩa" ở §2 chưa đúng, chứ không phải phải cố xoá cho
đủ số.

---

## ⛔ DỪNG ở §2 theo đúng điều kiện dừng của chính task (2026-08-25)

§1 (`SystemErrorFeed`) **đã xong** — xem commit `60c857b`. Phần §2 (xoá 48 signal) **dừng lại**,
đúng như mục "Rủi ro" của task tự quy định: *"Nếu số signal xoá được ít hơn hẳn dự kiến
(ví dụ < 30/48), dừng lại và ghi lý do — nhiều khả năng ranh giới 'cầu nối vs ngữ nghĩa' ở §2
chưa đúng, chứ không phải phải cố xoá cho đủ số."*

**Số xoá được ≈ 1/48.** Dưới ngưỡng 30 rất xa.

### Vì sao — tiền đề của §2 sai

§2 lập luận: *"Handler đăng ký qua `QtEventBridge` (`008D`) đã ở main thread ⇒ cầu nối không
còn lý do tồn tại."* Đúng — **nhưng chỉ với signal được emit từ handler của event bus.**

Đo thật cả 3 presenter:

| Presenter | Signal | Được truyền làm callback `.emit` vào controller/coordinator | Đăng ký bus |
| :--- | ---: | ---: | ---: |
| `dashboard_presenter` | 12 | **12** | 2 |
| `data_management_presenter` | 14 | **13** | 2 |
| `backtest_presenter` | 22 | **22** | 5 |
| **Tổng** | **48** | **47** | 9 |

**47/48 signal là cầu nối `worker thread → main thread`, không phải cầu nối bus-handler.** Chúng
được truyền vào controller dưới dạng callback (`emit_history_reloaded=self.ui_history_reloaded_signal.emit`,
…), và worker gọi callback đó để nhảy về main thread. Những worker này **không bao giờ đi qua
event bus**, nên `QtEventBridge` không thay thế được — nó chỉ bắc cầu cho event *trên bus*.

Bằng chứng mạnh nhất là chính file controller tự khai hợp đồng của nó
(`stream_lifecycle_controller.py`, dòng 10-13):

```
Threading contract:
- Worker methods (_run_load_history, _run_sync_and_start, _run_load_more_history) run in background threads.
- Background workers communicate with the main thread ONLY via Qt Signal callables (emit helpers).
- Main-thread slots (_on_load_history, _on_start_stream, etc.) execute UI state updates.
```

Xoá chúng mà không thay bằng cơ chế hop khác = đẩy cập nhật UI sang worker thread — đúng lớp lỗi
`BUG-031` (`QBasicTimer::start: Timers cannot be started from another thread`) đã tốn một ngày,
và đúng kiểu hỏng "app chạy, test xanh, màn hình không cập nhật" mà test offscreen không bắt.

### Cần user quyết trước khi đi tiếp

`008G` §2 như đang viết **không thực hiện được**. Ba hướng, không cái nào là "cứ xoá":

1. **Giữ 47 signal, chỉ làm §1/§3/§4.** Rẻ nhất, trung thực nhất. Signal worker→main là *đúng*
   cách làm trong Qt, không phải nợ kỹ thuật. Cái đáng dọn chỉ là 3 quy ước đặt tên lẫn lộn và
   payload thô (§3) — hai thứ đó vẫn làm được.
2. **Cho worker phát qua event bus** rồi presenter nghe qua `QtEventBridge`. Xoá được signal
   thật, nhưng biến mọi cập nhật UI nội bộ thành event toàn cục — trái §6 của epic
   (*"không thêm subscriber mới ngoài 3 Feed"*) và làm luồng khó lần hơn hẳn.
3. **Rút gọn số signal bằng cách gộp payload** (§3): ví dụ 4 signal history của Dashboard gộp
   thành 1 signal mang `HistoryUpdate`. Giảm *số lượng* mà vẫn giữ cơ chế hop đúng.

Đề xuất: **1 + 3**. Giữ cơ chế, gộp payload để giảm số signal một cách có lý do, và sửa lại §2
của task cho khớp thực tế thay vì ép chỉ tiêu 48.

---

## Xong 2026-08-25 (§1, §3, §4 — §2 dừng có lý do)

**Gate:** `RESULT: PASS`, **1738 passed** (trước task: 1715).

### §1 — ba Feed, dùng chung `BaseFeed`

| Feed | Thay cho |
| :--- | :--- |
| `SystemErrorFeed` | **0 subscriber** — `UiActionFailedEvent` + `runtime.tasks.failed` chảy vào hư không |
| `HealthFeed` | 2 bản `_trigger_initial_health_check()` tự chế event + 3 bản định dạng |
| `SyncProgressFeed` | 2 handler độc lập; chỉ 1 nơi có câu chữ |

`BaseFeed` ra đời đúng lúc có 3 consumer thật (`architecture-rule.md` §7.2). Nó **ép** chứ không
khuyên: tự bọc `QtEventBridge` nên không Feed nào quên hop về main thread; lớp con quên
`_subscribe()` thì **vỡ ngay lúc dựng** kèm tên lớp. `_publish()` thêm vào khi `HealthFeed` cần
nửa request — bus giữ ở thuộc tính name-mangled nên lớp con vẫn không thể subscribe vòng qua bridge.

**Lỗi thật tìm được:** bản định dạng của Backtest tự chọn khoá `database`+`event_bus` nên
**`Container` biến mất** khỏi màn đó. Feed giữ nguyên mọi component engine trả về → không chọn
lọc thì không mất được nữa. Sanity test khoá lại bằng cách assert **hai màn ra chuỗi giống hệt**.

### §3 — payload dataclass, cả 3 signal

| Signal | Trước | Sau |
| :--- | :--- | :--- |
| `ui_status_table_signal` | `Signal(str×6)` | `StatusRowUpdate` |
| `ui_gap_inspector_signal` | `Signal(str,str,int,int,float,list,list)` | `GapInspectorPayload` |
| `_backtestProgressSignal` | `Signal(int,str,int,int,float)` | `BacktestProgress` |

Cả ba đều có **tham số cùng kiểu nằm liền nhau** (6 `str`; 2 `int`+2 `list`; 2 `int`) — hoán nhầm
không sai kiểu nên `mypy` im lặng, Qt vẫn giao, UI chỉ hiển thị sai. Không có traceback để lần.

**Cố ý không đổi `upsert_row()`/`set_gap_inspector_data()`:** nguy hiểm nằm ở **biên signal**, nơi
giá trị qua hàng đợi cross-thread và không còn gì cạnh nhau để đối chiếu. Nơi gọi model trực tiếp
(`preview.py`, test) nằm ngay cạnh định nghĩa đọc được — đổi ở đó chỉ lan call site mà không mua
thêm an toàn.

### §4 — bus có `ILogger` thật, và nó lộ ra lỗi giấu

Không phải sửa "mất log" (`008C` đã lo). Nó quyết định lỗi **rơi vào đâu**: file log mà
`ci-local.ps1`'s "Run Log Scan" thật sự đọc.

Bật lên là gate đỏ ngay với **2 lỗi vốn vẫn xảy ra suốt nhưng vô hình**:

```
ListAvailableSymbolsQuery failed: object of type 'Mock' has no len()
SyncMarketDataCommand failed: 'Mock' object is not iterable
```

`Mock(spec=...)` ràng buộc **tên** method chứ không ràng buộc kiểu trả về, nên method nào fixture
quên cấu hình sẽ đưa `Mock` thô cho handler thật. Test vẫn xanh vì không assert vào đường đó.
**A/B để chắc:** tắt §4 giữ §3 → 2 lỗi biến mất ⇒ §4 **làm lộ**, không **gây ra**.

### Ngoài phạm vi task, sửa kèm vì làm gate đỏ

`BinanceWebsocketService.stop_stream()` log WARNING mỗi khi không có gì để dừng, mà adapter gọi
nó vô điều kiện lúc tắt app → mọi phiên không mở stream đều sinh WARNING. Dừng một stream chưa
chạy là **bình thường**, và giá trị trả về `False` đã nói điều đó → hạ xuống DEBUG. Có sẵn trong
log user chạy tay 2026-08-24, tức không do task này gây ra.
