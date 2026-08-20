# 🧭 Rà soát định hướng App — red flag & mâu thuẫn

> **Nguồn**: user hỏi thẳng *"bạn còn thấy vấn đề gì trong định hướng của app không? có
> red flag hay mâu thuẫn gì không?"* sau khi lập [Epic `BOT-073`](../backlog/BOT-073_realtime_tick_backtest_epic.md).
>
> **Phương pháp**: mọi phát hiện dưới đây đều **verify trực tiếp trên code/log/git thật**
> tại thời điểm viết — không suy đoán, không dựa vào trí nhớ. Mỗi mục ghi rõ cách kiểm
> chứng để bất kỳ ai cũng tự chạy lại được.
>
> **Trạng thái**: user đã đọc, chấp nhận, và yêu cầu ghi hết vào backlog để *"làm lại từ
> từ"*. File này là bản ghi gốc; cột "Ai sở hữu" trỏ tới task cụ thể.

---

## Bảng tổng hợp

| # | Phát hiện | Mức | Ai sở hữu |
| :---: | :--- | :---: | :--- |
| 1 | `-80.71%` trong log **~96% là phí giao dịch**, không phải chiến lược | 🔴 | ✅ [`BOT-079`](../completed/BOT-079_fee_transparency_and_trade_frequency.md) |
| 2 | **Không có bất kỳ** cơ chế chống overfitting nào | 🔴 | ✅ [`BOT-080`](../completed/BOT-080_out_of_sample_walk_forward.md) |
| 3 | Bot **không giao dịch được** — 21/46 task xong là backtest/chart | 🔴 | **Quyết định của user** (§3) |
| 4 | ~~Sắp có **3 backtest engine** với bất biến ngược nhau~~ → **đã đóng**: `BOT-023` bị huỷ, còn 2 engine | ✅ | [`BOT-023`](../cancelled/BOT-023_dynamic_backtest_engine.md) (đã huỷ 2026-08-18) |
| 5 | Agent tự động tối ưu **concurrency** vào vùng chưa có thread guard | 🟠 | [`BOT-068`](../completed/BOT-068_ui_thread_affinity_guard.md) (đã nâng ưu tiên) |
| 6 | Một test **đỏ vĩnh viễn** chưa từng pass | 🟠 | [`BOT-082`](../completed/BOT-082_fix_permanently_failing_interactive_shell_test.md) |
| 7 | Tài liệu-như-lời-hứa **trôi khỏi code** | 🟡 | [`BOT-074`](../backlog/BOT-074_execution_trigger_rule_inverted_lock.md) (ca cụ thể) + §7 (nguyên tắc) |

---

## 1. 🔴 `-80.71%` gần như hoàn toàn là phí giao dịch

### Bằng chứng

Log [`BUG-002`](../bug_report/completed/BUG-002.md):

```
19:13:21,033 - App.RunStaticBacktest - INFO -
    Static backtest complete for BTCUSDT: 807 trades, net profit -80.71%
```

`RunStaticBacktestCommand.fee_percent` mặc định `0.1`, `PaperExchange` thu **cả 2
chiều** (`_open()` và `_close()` đều tính phí).

```python
fees_only = (1 - 0.001) ** (2 * 807)  # = 0.1989  → -80.11%
observed = 1 - 0.8071  # = 0.1929  → -80.71%
gross = observed / fees_only  # = 0.9697  → -3.03%
```

### Diễn giải

- **Phí gây ra -80,11%** — chiếm **~96%** toàn bộ khoản lỗ.
- Edge *gross* của chiến lược: **-3,03%** trên 807 lệnh ≈ **-0,004%/lệnh** → về cơ bản
  là **hoà**, không có lợi thế cũng không thua vì hướng đi.
- 807 lệnh / 7 ngày dữ liệu 1m ≈ **1 lệnh mỗi 12 phút**.

### Vì sao đây là red flag *của app*, không phải của chiến lược

App đã có 13 metric kiểu TradingView, equity curve, drawdown, trade journal — nhưng
**không có chỗ nào nói cho user biết con số họ đang nhìn là phí**. Cụ thể đang thiếu:

- Tách `total_fees_paid` ra khỏi PnL trong `BacktestMetrics` (dữ liệu **đã có sẵn** ở
  `Trade.fees_paid`, chỉ là chưa tổng hợp lên).
- Cảnh báo tần suất giao dịch bất thường.
- Phân tích độ nhạy theo phí ("nếu phí 0% thì sao?").

→ Kính hiển vi rất tốt đang soi một mẫu vật trống, mà không báo là trống.

---

## 2. 🔴 Không có bất kỳ cơ chế chống overfitting nào

### Bằng chứng

```
grep -ri "walk.forward|out.of.sample|overfit|monte.carlo|in-sample" Tasks/ src/
→ 0 kết quả
```

Trong khi đó `BOT-044`/`046`/`047`/`048` đã hoàn thành **nguyên bộ máy tinh chỉnh tham
số**: form động theo schema, "Lưu & Re-Backtest", "Khôi phục Mặc định".

### Diễn giải

Đây là cỗ máy overfit không phanh: tinh chỉnh tham số trên **đúng một** khoảng lịch sử,
không tách train/test, không walk-forward, không kiểm định out-of-sample.

Với một sản phẩm backtest, đây là **lỗ hổng phương pháp luận lớn hơn hẳn vấn đề độ phân
giải tick** ([`BOT-073`](../backlog/BOT-073_realtime_tick_backtest_epic.md)).

⚠️ **Quan hệ ưu tiên đáng chú ý**: `BOT-073` làm kết quả *chân thực hơn về cơ chế*.
Nhưng nếu tham số đã overfit thì kết quả chân thực đó **vẫn vô nghĩa**. Overfitting nên
được xử lý **trước hoặc song song**, không phải sau.

---

## 3. 🔴 Bot không giao dịch được — và đó chưa bao giờ là ưu tiên

### Bằng chứng

- [`market_tick_event_handler.py`](../../src/application/event_handlers/market_data/market_tick_event_handler.py):
  `handle()` chỉ `logger.info(...)` rồi return. Comment: *"Here we will later invoke
  domain logic for strategy processing"*.
- [`BOT-008`](../backlog/BOT-008_live_trading_strategy_execution.md) — **P1**, ghi
  *"Sẵn sàng bắt đầu — mọi phụ thuộc đã hoàn thành"*, **chưa hề động tới**.
- `ls Tasks/completed/ | grep -icE "backtest|chart|trade_log|metric|indicator|strategy"`
  → **21** trên tổng **46** task đã xong.

### Diễn giải

Một app tên *trading bot*, hoàn thành 46 task, **chưa đặt được một lệnh nào**. Giá trị
hiện tại là "phần mềm phân tích", không phải "bot".

**Đây không phải lỗi** nếu là chủ đích (làm chắc backtest trước khi cho tiền thật vào là
lựa chọn hợp lý). Nhưng nếu là **trôi dạt** — backtest dễ làm hơn, dễ thấy thành quả
hơn, ít rủi ro hơn nên cứ làm tiếp — thì đáng dừng lại nhìn.

### 🔵 Đây là **quyết định của user, không phải task**

Không tạo task cho mục này. Câu hỏi cần user tự trả lời:

> Mục tiêu 3 tháng tới là **bot chạy được bằng tiền thật (dù thô)**, hay **công cụ
> nghiên cứu chiến lược tốt nhất có thể (chưa cần giao dịch)**?

Hai câu trả lời dẫn tới 2 thứ tự backlog hoàn toàn khác nhau. Ghi lại đây để lần sau
không phải suy luận lại.

---

## 4. 🟠 Sắp có 3 backtest engine với bất biến ngược nhau

### Bằng chứng

| Engine | Bất biến đã cam kết |
| :--- | :--- |
| Static ([`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅) | — |
| ~~Dynamic~~ ([`BOT-023`](../cancelled/BOT-023_dynamic_backtest_engine.md)) — **ĐÃ HUỶ 2026-08-18** | ~~**"phải khớp Static tuyệt đối"** — `assert dynamic_result == static_result`~~ |
| Realtime ([`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md)) | **"cố ý khác Static"** |

Hai engine replay, bất biến **ngược nhau**, cùng chạy trên một `PaperExchange`.

### Diễn giải — kèm tự nhận thiếu sót

Khi lập `BOT-073` tôi chỉ cảnh báo *"đừng nhầm với BOT-023"* mà **không chất vấn liệu
`BOT-023` còn nên tồn tại không**. Đó là thiếu sót.

Lý do nghi ngờ: giá trị của `BOT-023` là *play/pause/tốc độ để xem replay* — đó là mối
quan tâm **trình bày**, không phải engine. Mà `BOT-076` dù sao cũng phải có vòng lặp
tick + progress + cancel. Nhiều khả năng đúng là **1 engine tick + lớp điều khiển tốc độ
ở trên**, không phải 2 engine riêng.

→ Đã ghi chú thẳng vào `BOT-023`: **phải chốt quan hệ với `BOT-076` trước khi bắt đầu
một trong hai.** Quyết định muộn thì đắt (đã viết xong engine mới phát hiện thừa).

### ✅ ĐÃ CHỐT (2026-08-18) — user chọn phương án "Gộp"

`BOT-023` **bị huỷ**; hồ sơ chuyển sang
[`Tasks/cancelled/BOT-023_dynamic_backtest_engine.md`](../cancelled/BOT-023_dynamic_backtest_engine.md).
App còn đúng **2 engine backtest**: Static (`BOT-021` ✅) và Realtime (`BOT-076`).
Phần play/pause/tốc độ giữ lại nhưng là **lớp điều khiển** trên vòng lặp tick của
`BOT-076` (§3.5 của task đó), không phải engine thứ ba. Nghi vấn nêu ở mục này —
*"giá trị của `BOT-023` là mối quan tâm trình bày, không phải engine"* — được xác
nhận là đúng. Rủi ro "3 engine, 2 bất biến ngược nhau" coi như đã đóng.

---

## 5. 🟠 Agent tự động tối ưu concurrency vào vùng chưa có bảo vệ

### Bằng chứng

`git log` ~25 commit gần nhất (superproject) có nhiều commit tự động:

```
⚡ Bolt: Offload blocking DB fetch in asyncio coroutine to thread
⚡ Bolt: Batch concurrent fetches for GetHistoricalKlinesQuery   ← sửa stream_lifecycle_controller.py
🎨 Palette: [accessibility] Add keyboard shortcut hint...
Sentinel: Fix information disclosure in AuditService health check
Add tests for InteractiveShell / IExchangeClient / WMA / SignalGeneratedEvent...
```

Trong khi đó:

- [`BOT-038`](../backlog/BOT-038_intermittent_segfault_full_ui_integration_suite.md) —
  **segfault ngẫu nhiên đã biết** ở integration UI suite; đã điều tra 1 vòng rồi dừng.
- [`BOT-068`](../completed/BOT-068_ui_thread_affinity_guard.md) — **chưa làm**. Chính
  ROADMAP ghi: *"Engine hiện có **0** guard thread nào"*.
- [`BUG-001`](../bug_report/completed/BUG-001.md) — app từng treo vì chạm UI từ luồng nền.

### Diễn giải

Thứ tự đang **ngược**: thêm concurrency vào codebase chưa có cơ chế phát hiện sai luồng.
Đây là cách hiệu quả nhất để tạo bug không tái hiện được.

Khác với các mục khác, rủi ro này **tăng theo thời gian**: mỗi PR tối ưu đồng thời được
merge mà chưa có guard là một lớp rủi ro cộng thêm.

→ Đã ghi bối cảnh này vào `BOT-068` và đề xuất nâng ưu tiên.

---

## 6. 🟠 Một test đỏ vĩnh viễn — chưa từng pass

### Bằng chứng

`tests/unit/presentation/cli/test_interactive_shell.py:169`:

```python
with patch('src.presentation.cli.interactive_shell.logger.exception') as mock_logger:
```

Thiếu tiền tố `Sagittarius_Elite_Warrior.` → `ModuleNotFoundError: No module named 'src'`.
**Mọi import khác trong chính file đó đều có tiền tố đúng.**

Thêm vào bởi commit `9cd7ebf` *"Add tests for InteractiveShell start, wait_for_exit,
_run_loop, and do_help"* (12/08/2026) — mẫu commit của agent viết test tự động.

### Diễn giải

Hệ quả nguy hiểm hơn bản thân cái test: mỗi lần chạy suite đều thấy `1 failed`, nên **cả
người lẫn agent đều học được thói quen bỏ qua màu đỏ**.

Trong chính phiên làm việc sinh ra báo cáo này, tôi đã xác nhận "không liên quan" rồi đi
tiếp **5 lần** — đúng cơ chế mà một regression thật sẽ lọt qua.

---

## 7. 🟡 Tài liệu-như-lời-hứa đang trôi khỏi code

### Bằng chứng

[`OrderExecutionMenu.qml`](../../src/presentation/ui/components/OrderExecutionMenu.qml)
có comment mô tả rõ ý định *"the other 3 ... are shown-but-**disabled**"*, còn `ListModel`
làm **ngược lại hoàn toàn** — và không ai phát hiện suốt từ `BOT-022` tới nay.

### Diễn giải — kèm phần công bằng

Hệ thống tài liệu của repo này **thật sự tốt một cách bất thường**, và đã nhiều lần chứng
minh giá trị:

- `BOT-042` giữ được câu hỏi kiến trúc treo hàng tháng, tới khi user trả lời được.
- `BOT-072` root cause được điều tra sẵn trước khi ai đó bắt tay sửa.
- Nhiều quyết định ghi kèm *lý do*, cứu được các vòng điều tra lặp.

**Nhưng prose không thực thi được thì sẽ trôi.** Nguyên tắc rút ra:

> Chỗ nào tài liệu hứa một **bất biến**, chỗ đó nên có **guard test**, không phải câu văn.

`BOT-074` đã viết đúng theo hướng này (test assert cả 4 lựa chọn disabled, **cố tình vỡ**
khi ai đó mở khoá). Cân nhắc nâng thành rule trong
[`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md) — **chưa làm, chờ user
chốt** (không tự ý thêm rule).

---

## Điều đang làm tốt — ghi lại để không đánh mất khi sửa hướng

- **Kỷ luật sửa bug**: viết test tái hiện *trước*, và nó **thật sự đang chạy**, không phải
  khẩu hiệu — `BOT-072`, `BOT-065`, `BOT-062`, `BOT-061` đều theo đúng quy trình.
- **Ghi lại *lý do*, không chỉ *cái gì*** — thấy rõ ở gần như mọi task file.
- **Trung thực khi làm một phần** (`(một phần)`) thay vì giả vờ xong.
- **Bản năng "không xây máy móc trước khi có consumer"** (`BOT-030` từ chối promote hạ
  tầng QML vì mới 1 app dùng) — đúng và hiếm.

## Mâu thuẫn nhỏ hơn — ghi để không quên

| Mâu thuẫn | Ghi chú |
| :--- | :--- |
| `BOT-026` cam kết **"diff = 0 dòng"** cho `strategy_engine.py` | `BOT-042` **buộc phải** sửa file đó. Đã ghi trong `BOT-042` §4.3 là "hết hiệu lực có chủ đích". |
| Engine là *"framework dùng chung"* nhưng chỉ **1 consumer** | `BOT-030` từ chối promote hạ tầng QML vì *"đợi consumer thứ 2"*, nhưng `BOT-066`/`067`/`070` lại đẩy thẳng vào engine. Tiêu chuẩn không nhất quán — dù *cơ chế chống bug* khác *abstraction* nên có thể biện minh. |
| Thư viện chiến lược tham vọng, nguyên liệu thiếu | Chỉ **2 strategy** thật (`ema_crossover`, `multi_ema_trend_follower`). `BOT-052` cần ATR/ADX (**chưa có**), `BOT-053` cần swing high/low detection (**chưa có**), `Series` mặc định giữ **16 bar** — chính `BOT-043` đã ghi *"nhiều khả năng không đủ"*. |

---

📄 Liên quan: [Phân tích Lớp Lỗi Engine](engine_defect_class_analysis.md) ·
[Backtest Feature Status](backtest_screen_feature_status.md) · [ROADMAP](../ROADMAP.md)
