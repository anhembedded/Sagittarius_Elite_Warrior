# Epic: Realtime Backtest — chạy backtest theo tick, song song với Static

> Sinh ra từ yêu cầu trực tiếp của user: *"The backtest we use is something like
> static backtest, as TradingView. It could not describe what the bot trading real
> behaviour. Indicator could set on tf 1m, but realtime data feed every 1s. So every
> one sec, we must calculate the last candle and all last indicator. I want a
> realtime backtest. So I want 2 backtest strategies available on my app."*
>
> Kèm làm rõ sau đó về `calc_on_order_fills` của Pine Script (chạy lại tập lệnh ngay
> khoảnh khắc lệnh được khớp, thay vì chờ đóng nến).
>
> **Supersede scope** của [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md)
> — task đó không bị xoá, chỉ được chốt lại quyết định kiến trúc còn treo và trở
> thành task con của epic này (cùng cách `BOT-040` xử lý `BOT-022`/`BOT-024`).

## 1. Mục tiêu

App có **2 chế độ backtest dùng song song**, chọn được từ UI:

| Chế độ | Ngữ nghĩa | Dùng để |
| :--- | :--- | :--- |
| **Static** (đang có, `BOT-021` ✅) | Strategy chạy 1 lần/nến, tại nến đóng | So sánh nhanh nhiều chiến lược/tham số; kết quả tái lập 100% |
| **Realtime** (epic này) | Strategy chạy lại mỗi tick trong nến đang hình thành | Kiểm chứng hành vi bot sẽ chạy live |

Hai chế độ **bắt buộc dùng chung** `PaperExchange`/`Trade`/`BacktestMetrics`/
`BacktestResult` — nếu không, 2 kết quả không so sánh được với nhau, mà so sánh
chính là lý do tồn tại của việc có 2 chế độ.

## 2. Hiện trạng — đã verify trực tiếp trên code, không suy đoán

### 2.1. Chưa hề có bot live để mà "không khớp"

[`market_tick_event_handler.py`](../../src/application/event_handlers/market_data/market_tick_event_handler.py)
— `handle()` chỉ `logger.info(...)` rồi return. Comment trong chính file:
*"Here we will later invoke domain logic for strategy processing"*. Dòng log
`Processing tick for ETHUSDT at ...` thấy trong [`BUG-002`](../bug_report/BUG-002.md)
là **log suông**, không chạy chiến lược nào. Live trading thật = `BOT-008`, vẫn ở
backlog.

**Hệ quả về thứ tự làm việc**: đây là **lợi thế, không phải vấn đề** — chốt được
ngữ nghĩa tick ở backtest **trước** khi viết `BOT-008` thì live chỉ việc bám theo,
thay vì viết live xong rồi phải sửa backtest cho khớp (hoặc ngược lại).

### 2.2. Toàn hệ thống hôm nay nhất quán "bar-close only"

- Static backtest: `engine.on_tick(candle)` đúng 1 lần/nến đã đóng.
- Dev Board live ([`dashboard_presenter.py`](../../src/presentation/ui/screens/dashboard/dashboard_presenter.py))
  — chỉ `self._script_runner.feed(candle)` khi `is_closed=True`; nến chưa đóng
  **chỉ vẽ lên chart** (`update_last_candle`), không nuôi indicator.

Nên hiện tại **không có mismatch nào**. Mismatch sẽ xuất hiện đúng lúc `BOT-008`
ra đời, nếu lúc đó live tính theo tick còn backtest thì không.

### 2.3. Khoảng trống sau khi khớp lệnh (câu hỏi `calc_on_order_fills`)

Vòng lặp trong [`run_static_backtest/handler.py`](../../src/application/use_cases/backtest/run_static_backtest/handler.py)
mỗi nến chạy đúng thứ tự: *fill lệnh chờ ở giá open* → *`engine.on_tick(nến đầy đủ)`*
→ *ghi equity*. Trải theo thời gian:

| Thời điểm | Việc xảy ra |
| :--- | :--- |
| Đóng nến N | `on_tick(nến N)` → Signal → treo vào `pending_signal` |
| **Open nến N+1** | **`exchange.fill(...)` — lệnh khớp tại đây** |
| Suốt nến N+1 | **Không có gì chạy** |
| Đóng nến N+1 | `on_tick(nến N+1)` — lần đánh giá kế tiếp |

Khoảng trống giữa *lúc khớp* và *lần chạy lại* là **trọn một cây nến**.

**Công bằng mà nói**: đây khớp chính xác hành vi **mặc định** của Pine
(`calc_on_order_fills = false`) — không phải làm sai, mà là **chưa có tuỳ chọn bật
cái kia**.

### 2.4. Bug thật đã tìm ra: checkbox mời bật rồi im lặng bỏ qua

[`OrderExecutionMenu.qml`](../../src/presentation/ui/components/OrderExecutionMenu.qml)
có comment ghi rõ ý định *"the other 3 ... are shown-but-**disabled**"*, nhưng dữ
liệu thật thì **ngược lại**: `"On bar close"` (cái duy nhất chạy thật) bị
`locked: true` → làm mờ; 3 cái chưa làm được thì `locked: false` → bấm được bình
thường. Và `grep` toàn repo: **không có `executionTrigger` nào ở Python** — trạng
thái checkbox không bao giờ rời khỏi QML.

→ Tách riêng thành [`BOT-074`](BOT-074_execution_trigger_rule_inverted_lock.md),
làm ngay, không chờ epic.

## 3. Quyết định kiến trúc đã chốt

`BOT-042` §3 từng liệt kê 2 hướng và ghi *"**Không tự chọn (a) hay (b)** — quay lại
hỏi user"*. User đã chọn:

> **Hướng (b)**: indicator **tính lại mỗi tick** — giá trị RSI/EMA "sống" thay đổi
> liên tục trong nến chưa đóng, giống `calc_on_every_tick=true` của TradingView.

Tương tự, `BOT-040` §2.1 từng ghi *"On order filled — ❓ chưa rõ nghĩa trong ngữ
cảnh backtest"*. User đã làm rõ: đó là `calc_on_order_fills` — **chạy lại tập lệnh
ngay khoảnh khắc lệnh khớp**, không chờ đóng nến.

## 4. Chướng ngại kỹ thuật cốt lõi — và vì sao nó **không** nặng như vẻ ngoài

Indicator là **stateful và không hoàn tác được**:

- [`ema.py`](../../src/domain/indicators/ema.py) — `self._ema` bị **ghi đè tại chỗ**.
  Gọi 60 lần/phút thay vì 1 lần → EMA(12) trên khung 1m biến thành EMA trên ~12
  mẫu-giây. **Sai hoàn toàn**, không phải sai lệch nhỏ.
- [`series.py`](../../src/domain/scripting/series.py) — `push()` luôn `appendleft`
  vĩnh viễn → `crossed_above` sẽ so 2 tick **trong cùng 1 bar** như thể 2 bar khác
  nhau → tín hiệu giả hàng loạt.

Đây **không phải bug** — là thiết kế có chủ đích: docstring `IIndicator` ghi rõ state
được giữ giữa các lần gọi để *"the exact same `update()` path serves both batch and
incremental"*.

**Tin tốt**: về mặt toán học phần lớn indicator tính "tạm" được **O(1)** từ state đã
chốt + giá hiện tại (EMA chỉ là `(v - ema_committed) * mult + ema_committed` mà
**không gán**). Nên **không cần** snapshot/rollback nặng nề — chỉ cần tách khái niệm
*provisional* khỏi *commit*. Cái đắt là **đổi contract `IIndicator`**, vốn dùng chung
bởi cả Dev Board lẫn static backtest.

## 5. Bảng task con

| Task | Tên | Phụ thuộc | Ghi chú |
| :--- | :--- | :---: | :--- |
| [**BOT-074**](BOT-074_execution_trigger_rule_inverted_lock.md) | **Bug — Execution Trigger Rule: cờ `locked` đảo ngược** | — | Nhỏ, độc lập, **làm ngay**. Không chờ phần còn lại của epic. |
| [**BOT-075**](BOT-075_tick_data_feasibility_spike.md) | **Spike — khả thi & chi phí dữ liệu tick** | — | **Đo, không đoán.** Có thể đổi cả thiết kế → phải xong trước `BOT-076`. |
| [**BOT-042**](BOT-042_tick_level_strategy_engine_support.md) | **Provisional vs Commit cho `IIndicator`/`Series`** | `BOT-020` ✅, `BOT-026` ✅ | Đã chốt hướng (b). Thay đổi contract tầng domain — rủi ro cao nhất epic. |
| [**BOT-076**](../in_progress/BOT-076_realtime_backtest_engine.md) | **Realtime Backtest Engine** | `BOT-042`, `BOT-075` | Chế độ backtest thứ 2 thật sự. |
| [**BOT-077**](BOT-077_calc_on_order_fills.md) | **`calc_on_order_fills`** | `BOT-076` | Giá trị thấp hơn hẳn 3 task trên — xem §6. |

## 6. `calc_on_order_fills` **không phải** cách đúng để giải quyết nỗi lo Stop Loss

Ghi rõ ở đây để không ai (kể cả chính chúng ta 3 tháng sau) làm sai thứ tự ưu tiên.

User lo: *"lệnh khớp phút thứ 10, phải chờ tới phút 60 code mới chạy để đặt Stop Loss
— trễ 50 phút này có thể cháy tài khoản."*

Pine **buộc phải** có `calc_on_order_fills` vì trong Pine, muốn đặt SL thì phải gọi
`strategy.exit()` **từ trong script** → script không chạy thì không đặt được. Đó là
**giới hạn của Pine**, không phải quy luật tự nhiên.

Sàn thật (Binance) không hoạt động vậy: SL/TP là **lệnh nằm sẵn trên sàn**
(bracket/OCO), đặt kèm ngay lúc vào lệnh, sàn tự canh 24/7 — **bot không cần chạy lại
lần nào**, bot sập nguồn thì SL vẫn còn đó.

[`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) đã định hướng đúng theo
mô hình này rồi (*"SL/TP tự đóng vị thế, kiểm tra bằng `high`/`low` mỗi bar"*). Nếu
SL/TP là **thuộc tính của vị thế** do `PaperExchange` tự canh thì kịch bản "cháy tài
khoản vì trễ 50 phút" **không thể xảy ra**, kể cả khi vĩnh viễn không làm `BOT-077`.

→ **`BOT-041` mới là thứ giải quyết nỗi lo an toàn, không phải `BOT-077`.**

`calc_on_order_fills` vẫn cần, nhưng cho những thứ **thật sự đòi hỏi logic strategy**
sau khi biết giá khớp *thực tế*: pyramiding (tính size lệnh 2 theo giá khớp thật),
đảo chiều tức thì trong cùng nến, SL động theo giá khớp thật (lệch giá dự kiến do
slippage).

## 7. Bất biến trong tài liệu sẽ phải sửa lại lời hứa

`BOT-020` hiện đảm bảo *"batch ≡ incremental"* bằng cách cả 2 mode đi qua đúng 1
`_process_one`. Thêm tick thì **Static và Realtime không thể ra cùng kết quả** — **và
đó là đúng, không phải lỗi.**

Nhưng **phải ghi rõ ra giấy** (việc của `BOT-042`), vì tài liệu hiện đang hứa ngược
lại. Không nói rõ thì người sau sẽ tưởng Realtime đang bug.

✅ **2026-08-18 — `BOT-023` (Dynamic Backtest Engine) đã bị huỷ**
([hồ sơ huỷ](../cancelled/BOT-023_dynamic_backtest_engine.md)), theo quyết định của
user. Trước đây mục này cảnh báo *"đừng nhầm `BOT-023` với epic này"* — giờ nguồn gây
nhầm đó không còn: nó vẫn bar-by-bar, chỉ thêm tua/pause/tốc độ để *xem*, nên **không**
giải quyết yêu cầu của epic này, và ràng buộc parity `assert dynamic_result ==
static_result` của nó cũng đi theo. App còn đúng **2 engine**: Static (`BOT-021` ✅) và
Realtime (`BOT-076`). Phần play/pause/tốc độ vẫn giữ, nhưng là **lớp điều khiển** nằm
trên vòng lặp tick của `BOT-076` (§3.5 của task đó), không phải engine riêng.

## 8. Rủi ro toàn epic

- **Fidelity ảo — rủi ro lớn nhất.** Tick 1s **vẫn không phải tick thật** (Binance
  `aggTrade` có thể có nhiều lệnh trong 1 giây). Realtime backtest tạo *cảm giác*
  giống thật hơn mức nó thật sự giống — vẫn thiếu **slippage, độ trễ mạng, orderbook
  depth, partial fill**. Nếu mục tiêu là "tả đúng hành vi bot thật" thì độ phân giải
  tick chỉ là **1 trong 4-5 nguồn sai lệch**. Phải ghi giới hạn này lên UI hoặc báo
  cáo kết quả, kẻo tin nhầm vào con số đẹp.
- **Dữ liệu 60×**: 1 năm/1 symbol ở 1s ≈ **31,5 triệu dòng** thay vì 525K. Đây là lý
  do `BOT-075` phải đi trước.
- **Runtime**: log `BUG-002` cho thấy static backtest **10.079 nến mất ~1,5 giây**
  (19:13:19,548 → 19:13:21,033). Cùng 7 ngày đó ở 1s = **604.800 tick** → ~90 giây
  nếu tuyến tính, **chưa tính** chi phí tính lại N indicator mỗi tick. Hết thời "bấm
  nút ra ngay" — cần progress + cancel thật (`CancellationToken` đã có sẵn).
- **Đụng domain dùng chung**: `BOT-042` sửa `IIndicator`/`Series` — dùng bởi Dev Board
  live, static backtest, indicator scripts (`BOT-032`), strategies (`BOT-026`). Mọi
  thay đổi phải giữ đường bar-close hiện tại **không đổi hành vi 1 chút nào**.

## 9. Phụ thuộc & liên quan

- [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅ —
  `PaperExchange`/`Trade`/`BacktestResult`, dùng chung cho cả 2 chế độ.
- [`BOT-020`](../completed/BOT-020_indicator_strategy_engine_core.md) ✅,
  [`BOT-026`](../completed/BOT-026_concrete_strategy_foundation.md) ✅ — nơi thay đổi
  contract xảy ra.
- [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) — **không phụ thuộc
  epic này**, nhưng chính xác hơn hẳn khi có tick (với nến 1m không biết `high` hay
  `low` chạm trước; có tick thì biết). Cân nhắc làm `BOT-076` trước `BOT-041` nếu
  muốn SL/TP intra-bar đúng thật.
- [`BOT-008`](BOT-008_live_trading_strategy_execution.md) — live thật, **nên bám theo
  ngữ nghĩa epic này chốt**, không tự định nghĩa lại.
- [`BOT-040`](BOT-040_backtest_screen_full_feature_epic.md) §2.1 — 4 Execution Trigger
  Rule; epic này mở khoá 3 cái còn lại.
