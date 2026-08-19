# Nhiệm vụ: Realtime Backtest Engine — chế độ backtest thứ 2, chạy theo tick

> Thuộc Epic [`BOT-073`](../backlog/BOT-073_realtime_tick_backtest_epic.md).
> ✅ **2026-08-19 — hết chặn.** [`BOT-042`](../backlog/BOT-042_tick_level_strategy_engine_support.md)
> (contract provisional/commit — cả 4 task con A/B/C/D) và
> [`BOT-075`](../backlog/BOT-075_tick_data_feasibility_spike.md) (spike chi phí dữ liệu, kết luận
> khả thi có điều kiện) đều đã xong. Task này giờ sẵn sàng bắt đầu.
>
> 🟡 **Tiến độ 2026-08-19**: §3.1 (use case & command) và §3.2 (vòng lặp replay)
> **xong** — `RunRealtimeBacktestCommand`/`RunRealtimeBacktestCommandHandler` thật,
> đăng ký DI, 12 test mới (8 unit handler + 4 sanity DI) cộng toàn bộ 1369 test
> `tests/unit/` cũ giữ nguyên. §3.4 (test) xong phần cốt lõi (chốt-đúng-1-lần-bar,
> không tín hiệu giả, degenerate khớp Static, cộng 1 test phát hiện thêm về
> tick-gap). **Còn lại: §3.3 (UI — mở khoá Execution Trigger Rule, nối dây
> `IThreadManager`/`CancellationToken` từ Presenter, hiển thị Realtime vs Static)
> và §3.5 (replay control, tuỳ chọn không chặn "task xong").**
>
> 📌 **2026-08-18 — task này giờ là engine replay DUY NHẤT của app.**
> `BOT-023` (Dynamic Backtest Engine) **đã bị huỷ** theo quyết định của user
> ([hồ sơ huỷ](../cancelled/BOT-023_dynamic_backtest_engine.md)): nó vẫn chạy
> bar-by-bar nên không trả lời được yêu cầu gốc, và giá trị riêng của nó
> (play/pause/tốc độ) là **lớp trình bày** chứ không phải engine thứ hai.
> Hệ quả: phần replay control ấy **thuộc về task này** — xem §3.5 mới.
> Đừng dựng lại engine replay thứ hai.

## 1. Mục tiêu

Chế độ backtest thứ 2 chạy được thật, chọn từ UI, đúng yêu cầu gốc của user: *"every
one sec, we must calculate the last candle and all last indicator"*.

Sau task này app có **2 chế độ dùng song song**:

| | Static (`BOT-021` ✅) | Realtime (task này) |
| :--- | :--- | :--- |
| Strategy chạy | 1 lần/nến, tại nến đóng | Mỗi tick trong nến đang hình thành |
| Indicator | Chốt mỗi nến | Tính tạm mỗi tick, chốt khi nến đóng |
| Fill | Open nến kế tiếp | Giá tick thật |
| Kết quả | Tái lập 100% | **Cố ý khác Static** (xem §5) |

## 2. Ràng buộc kiến trúc số 1: dùng chung tầng khớp lệnh & đo lường

`PaperExchange`, `Trade`, `BacktestMetrics`, `BacktestResult` — **dùng chung 100%,
không fork, không bản sao "cho tick"**.

Lý do: lý do tồn tại của việc có 2 chế độ là **so sánh chúng với nhau**. Nếu 2 bên
tính metric bằng 2 đường code khác nhau thì mọi khác biệt quan sát được đều lẫn lộn
giữa "khác vì cơ chế" và "khác vì lỗi cài đặt" → cả epic mất giá trị.

Khác biệt **chỉ được phép nằm ở**: (1) vòng lặp replay, (2) thời điểm indicator chốt,
(3) giá/thời điểm fill.

## 3. Các bước thực hiện

### 3.1. Use case & command

- [x] `RunRealtimeBacktestCommand` + handler, đặt cạnh `run_static_backtest/`
      (`src/application/use_cases/backtest/run_realtime_backtest/`). **Không** sửa
      `RunStaticBacktestCommandHandler` — 2 handler tách biệt, giống cách `BOT-021`
      đã cố ý tách khỏi `RunBacktestCommandHandler` (Dynamic).
- [x] Field: kế thừa nguyên bộ của `RunStaticBacktestCommand` (`symbol`/`interval`/
      `strategy_key`/`strategy_params`/`initial_balance`/`fee_percent`/`start_time`/
      `end_time`/`limit`) **cộng** độ phân giải tick (`BOT-075` §3.4 chốt hình thức:
      field riêng hay `TimeFrame`). → Đã chốt: field riêng `tick_resolution: TimeFrame`,
      validator từ chối `tick_resolution` thô hơn `interval`.
- [x] ⚠️ `interval` (khung indicator, vd `1m`/`5m`/`1h`) và độ phân giải tick (vd
      `1s`) là **2 thứ khác nhau, hoàn toàn độc lập** — đây chính là điểm mấu chốt
      user nêu ra ("indicator could set on tf 1m, but realtime data feed every 1s").
      User nhắc lại rõ hơn (2026-08-18): *"phải chạy chiến thuật từng giây, cho dù tf
      có là 5 phút đi chăng nữa"* — tức là **mọi** khung đều đánh giá lại mỗi giây,
      không phải chỉ khung nhỏ; nến `5m` đang hình thành vẫn được cập nhật và đánh
      giá 300 lần trước khi nó đóng. Đặt tên field sao cho không ai nhầm được.
- [x] Đăng ký DI trong `binance_bot_module.py` + sanity test
      (`test_backtest_screen_di_sanity.py`) — theo đúng rule "mọi feature ship kèm
      sanity test". Cả 8 test sanity pass, gồm test mới cho
      `RunRealtimeBacktestCommand` resolve đúng handler qua DI container thật.

### 3.2. Vòng lặp replay

- [x] Mỗi tick: cập nhật nến đang hình thành (OHLC chạy) → indicator **tính tạm**
      (`BOT-042`) → strategy đánh giá → có Signal thì `PaperExchange` khớp **tại giá
      tick**.
- [x] Khi biên giới bar đi qua: **chốt** indicator + `Series.push()` đúng 1 lần cho
      bar vừa đóng. Đây là chỗ dễ sai nhất — sai thì hoặc mất 1 bar, hoặc chốt 2 lần.
      → **Bẫy thật gặp phải lúc code**: thiết kế ban đầu gọi
      `on_forming_bar_tick()` vô điều kiện cho MỌI tick, kể cả tick cuối cùng đóng
      bar — dẫn tới tick đó bị đánh giá 2 lần (1 lần provisional, 1 lần commit ngay
      sau) với **cùng dữ liệu**, sinh tín hiệu giả đúp trên mọi bar. Sửa bằng cách
      phát hiện "tick cuối của bar" qua `tick.close_time >= bar_end` — tick đó CHỈ đi
      qua `on_tick()` (commit), không qua `on_forming_bar_tick()` nữa. Có test riêng
      xác nhận (`test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close`).
- [x] Equity curve: chốt **theo bar**, không theo tick (nếu không, `equity_curve` sẽ
      to gấp 60× và `BacktestMetrics.max_drawdown` sẽ tính trên tập điểm khác hẳn
      Static → mất khả năng so sánh). Ghi rõ quyết định này vào docstring.
- [ ] Chạy nền qua `IThreadManager` + `CancellationToken` (pattern đã có từ
      `BOT-034`), phát progress event — với 604.800 tick/tuần thì UI **bắt buộc** phải
      huỷ được giữa chừng. **Chưa làm** — handler đã hỗ trợ `cancellation_requested`/
      `progress_callback` cooperative (đúng contract `ICommandHandler`), nhưng việc
      submit qua `IThreadManager` từ Presenter là phần việc của §3.3 (UI), chưa đụng.

### 3.3. UI

> 📌 **2026-08-19 — xác nhận với user: KHÔNG vẽ chart realtime theo từng tick.**
> Vòng lặp §3.2 chạy hết tốc độ trong nền (progress + Hủy như Static hôm nay);
> chart chỉ **render đúng 1 lần** khi có `BacktestResult` cuối cùng — giống hệt
> cách Static Backtest hoạt động, không phải animation tick-by-tick. Play/
> pause/tốc độ phát ở §3.5 (nếu làm) chỉ đổi **tốc độ vòng lặp tính toán nền**,
> không phải "vẽ lại chart mỗi tick" — 2 việc khác nhau, đừng nhầm. Quyết định
> này còn vì lý do kỹ thuật: native chart (`BOT-098F`) hiện chỉ hỗ trợ nạp
> full-replace-snapshot, không có đường incremental per-tick an toàn — vẽ
> realtime thật sẽ mở thêm hẳn 1 mảng việc ngoài phạm vi epic này.
>
> **Sequence — progress bar cập nhật nhiều lần, chart vẽ đúng 1 lần**, tái
> dùng nguyên cơ chế `set_backtest_progress()`/`_backtestProgressSignal` mà
> Static Backtest (`BOT-034`/`BOT-095C`) đã có, không xây mới:
>
> ```mermaid
> sequenceDiagram
>     autonumber
>     actor User
>     participant VM as BackTestViewModel (QML progress bar)
>     participant P as BackTestPresenter
>     participant TM as IThreadManager (background thread)
>     participant H as RunRealtimeBacktestCommandHandler
>     participant PE as PaperExchange
>
>     User->>P: Bấm "Chạy Backtest" (mode = Realtime)
>     P->>TM: submit(RunRealtimeBacktestCommand, progress_callback, cancellation_requested)
>     TM->>H: execute(command) [background thread]
>
>     loop Mỗi tick trong cửa sổ backtest (vd 604.800 tick/7 ngày)
>         H->>H: cập nhật nến đang hình thành + indicator tính TẠM (BOT-042B)
>         H->>PE: khớp lệnh tại giá tick nếu có Signal
>         alt Biên bar đi qua
>             H->>H: CHỐT indicator + Series.push() đúng 1 lần (BOT-042C)
>         end
>         opt Định kỳ (không phải mỗi tick — coalesce, xem logging-rule §4)
>             H-->>P: progress_callback(phase, completed, total, elapsed)
>             P->>VM: set_backtest_progress(percent, label) [qua Qt signal, thread-safe]
>             VM-->>User: Progress bar + % + ETA cập nhật
>         end
>         opt User bấm Hủy giữa chừng
>             User->>P: Bấm "Hủy"
>             P->>H: cancellation_requested() = true
>             H-->>TM: raise BacktestCancelled
>             TM-->>P: BacktestCancelled
>             P->>VM: hiện trạng thái đã hủy, KHÔNG vẽ chart
>         end
>     end
>
>     H-->>TM: trả về BacktestResult đầy đủ (klines + trades + equity + metrics)
>     TM-->>P: BacktestResult [qua Qt signal, thread-safe]
>     P->>VM: set_stat_cards() + set_result() + render chart 1 LẦN DUY NHẤT
>     VM-->>User: Kết quả cuối cùng hiện ra — không có bước vẽ trung gian nào trước đó
> ```
>
> Điểm mấu chốt: nhánh `opt Định kỳ` (progress bar) và nhánh cuối (render
> chart) là **2 con đường hoàn toàn tách biệt** — progress bar không bao giờ
> đụng tới `ChartCard`/`NativeBacktestChartHostAdapter`, chart chỉ nhận dữ
> liệu đúng 1 lần từ `BacktestResult` cuối cùng, giống hệt luồng Static hôm
> nay (`_on_chart_data_ready_for_action` → `_on_chart_data_ready`).

- [ ] Mở khoá lựa chọn tick trong
      [`OrderExecutionMenu.qml`](../../src/presentation/ui/components/OrderExecutionMenu.qml)
      và **nối dây thật** xuống `BackTestViewModel` → command. Đây là phần
      [`BOT-074`](../completed/BOT-074_execution_trigger_rule_inverted_lock.md) cố ý **không** làm
      (chưa có consumer); giờ đã có.
- [ ] Test guard của `BOT-074` sẽ vỡ ở bước này — **đúng như thiết kế**. Sửa nó cho
      khớp trạng thái mới, đừng xoá.
- [ ] Hiển thị rõ trên kết quả: đây là Realtime hay Static (kèm độ phân giải tick).
      Hai kết quả trông giống hệt nhau mà ngữ nghĩa khác nhau là bẫy hiểu nhầm.

### 3.4. Test

- [x] Test "chốt đúng 1 lần/bar": feed N tick trải qua M biên bar → indicator phải đã
      chốt đúng M lần, `Series` dài đúng M. →
      `test_bars_commit_exactly_once_each_not_once_per_tick` — **log-proved** (đọc
      đúng M dòng `bar_committed` qua `caplog`, không chỉ suy ra từ độ dài
      `equity_curve`), đúng yêu cầu "khi test phải có log proved".
- [x] Test tín hiệu giả: 2 tick trong **cùng** 1 bar vượt ngưỡng cross **không được**
      sinh 2 tín hiệu như thể 2 bar (bẫy đã nêu ở `BOT-042` §3 câu 2). → Bất biến này
      đã có test riêng ở tầng `Series`/`StrategyEngine` (`BOT-042C`/`D`); ở tầng
      handler này, `test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close`
      chứng minh không có tick nào (kể cả tick đóng bar) bị đánh giá 2 lần.
- [x] Test degenerate: chạy Realtime với độ phân giải tick **bằng đúng** `interval`
      (mỗi bar đúng 1 tick) → kết quả **phải khớp Static**. Đây là cách duy nhất kiểm
      chứng 2 đường code không lệch nhau vì lỗi cài đặt, khi mà nói chung chúng cố ý
      khác nhau (xem §5). → `test_one_tick_per_bar_matches_static_exactly`, dùng
      `EmaCrossoverStrategy` thật (không phải stub) chạy qua cả 2 handler, so khớp
      `trades`/`equity_curve` bit-for-bit.
- [x] Bonus, phát hiện lúc code: test khoảng trống dữ liệu
      (`test_a_tick_gap_between_bars_is_logged_and_force_commits_the_stale_bar`) —
      thiếu tick giữa 2 bar phải log cảnh báo rõ ràng + tự chốt bar dở dang, không
      được lặng lẽ mất dữ liệu.

### 3.5. Replay control (thừa kế từ `BOT-023` đã huỷ)

Phần này trước đây thuộc `BOT-023`. Sau khi task đó bị huỷ, nó về đây — nhưng **là
lớp điều khiển tốc độ trên vòng lặp §3.2, không phải engine thứ hai**.

- [ ] Có thể **chạy hết tốc độ** (mặc định, không throttle) — đây là chế độ dùng để
      lấy kết quả, và là chế độ duy nhất `BOT-077`/so sánh Static-vs-Realtime cần.
- [ ] **Tuỳ chọn** (làm sau cũng được, không chặn "task xong"): pause/resume + chọn
      tốc độ phát để *xem* diễn biến. Nếu làm, đi qua command riêng
      (`PauseBacktestCommand`/`ResumeBacktestCommand`/`SetReplaySpeedCommand`) tác
      động lên **cùng một** vòng lặp §3.2 — tuyệt đối không fork một vòng lặp
      "để xem" riêng, vì đó đúng là sai lầm khiến `BOT-023` bị huỷ.
- [ ] Tốc độ phát **không được** làm đổi kết quả: chạy 1x, 20x hay Instant trên cùng
      input phải cho `BacktestResult` giống hệt nhau. Cần 1 test khẳng định điều này
      (throttle chỉ là `sleep` giữa các tick, không đụng thứ tự tính toán).

## 4. Rủi ro / Lưu ý

- **Không còn engine replay thứ hai để nhầm lẫn nữa** — `BOT-023` (Dynamic) đã bị
  huỷ ([hồ sơ](../cancelled/BOT-023_dynamic_backtest_engine.md)). Nếu bắt gặp tài
  liệu cũ nào còn nói "Dynamic mode" như một engine sắp làm, đó là tài liệu lạc hậu.
  Lưu ý code `run_backtest/` (Dynamic cũ) **vẫn còn trong repo**, chỉ phát
  `MarketTickEvent`, không có consumer — chốt tái dùng hay xoá **trước khi** bắt đầu
  §3.2, đừng để nó lửng lơ cạnh vòng lặp mới.
- Cám dỗ: nhét tick vào thẳng handler Static bằng một cờ `if`. Đừng — hai vòng lặp có
  bất biến khác nhau (Static: 1 lần/bar; Realtime: nhiều lần/bar + chốt ở biên), nhồi
  chung sẽ làm cả hai khó suy luận và làm hỏng khả năng so sánh.
- Runtime: xem số đo `BOT-075` §3.3 trước khi hứa gì với UI.
- **Fidelity ảo** (`BOT-073` §8): tick 1s vẫn không phải tick thật; vẫn thiếu
  slippage/latency/orderbook depth/partial fill. Nên nói rõ giới hạn ở chỗ hiển thị
  kết quả.

## 5. Bất biến: Realtime **cố ý** không khớp Static

Ghi rõ để người sau không đi tìm "bug" không tồn tại:

- Static và Realtime **được phép và được kỳ vọng** cho kết quả khác nhau trên cùng dữ
  liệu — vì chúng mô hình hai thứ khác nhau (quyết định lúc đóng nến vs quyết định
  trong lòng nến).
- Ngoại lệ **duy nhất** phải khớp: trường hợp degenerate ở §3.4 (1 tick/bar).
- `BOT-042` §4.2 có action item sửa lại lời hứa "batch ≡ incremental" của `BOT-020`;
  nếu task đó chưa làm phần ghi tài liệu, **không được** coi task này là xong.

## 6. Phụ thuộc

- [`BOT-042`](../backlog/BOT-042_tick_level_strategy_engine_support.md) ✅ — provisional/commit
  đầy đủ cho `IIndicator`/`Series`/`StrategyEngine`.
- [`BOT-075`](../backlog/BOT-075_tick_data_feasibility_spike.md) ✅ — spike xong, khả thi có
  điều kiện (chạy nền + progress/cancel, nên cho chọn độ phân giải).
- [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅ —
  `PaperExchange`/`BacktestResult` dùng chung.
- [`BOT-074`](../completed/BOT-074_execution_trigger_rule_inverted_lock.md) — nên xong trước để UI
  ở trạng thái trung thực trước khi mở khoá.
- [`BOT-041`](../backlog/BOT-041_stop_loss_take_profit_and_risk_sizing.md) — không chặn nhau,
  nhưng SL/TP intra-bar **chỉ chính xác thật** khi có tick → cân nhắc làm task này
  trước.
- [`BOT-077`](../backlog/BOT-077_calc_on_order_fills.md) — consumer tiếp theo, chặn bởi task này.
