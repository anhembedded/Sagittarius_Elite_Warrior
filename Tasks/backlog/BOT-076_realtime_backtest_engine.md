# Nhiệm vụ: Realtime Backtest Engine — chế độ backtest thứ 2, chạy theo tick

> Thuộc Epic [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md).
> **Chặn bởi** [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md) (contract
> provisional/commit) và [`BOT-075`](BOT-075_tick_data_feasibility_spike.md) (chi phí
> dữ liệu — có thể đổi thiết kế).
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

- [ ] `RunRealtimeBacktestCommand` + handler, đặt cạnh `run_static_backtest/`
      (`src/application/use_cases/backtest/run_realtime_backtest/`). **Không** sửa
      `RunStaticBacktestCommandHandler` — 2 handler tách biệt, giống cách `BOT-021`
      đã cố ý tách khỏi `RunBacktestCommandHandler` (Dynamic).
- [ ] Field: kế thừa nguyên bộ của `RunStaticBacktestCommand` (`symbol`/`interval`/
      `strategy_key`/`strategy_params`/`initial_balance`/`fee_percent`/`start_time`/
      `end_time`/`limit`) **cộng** độ phân giải tick (`BOT-075` §3.4 chốt hình thức:
      field riêng hay `TimeFrame`).
- [ ] ⚠️ `interval` (khung indicator, vd `1m`/`5m`/`1h`) và độ phân giải tick (vd
      `1s`) là **2 thứ khác nhau, hoàn toàn độc lập** — đây chính là điểm mấu chốt
      user nêu ra ("indicator could set on tf 1m, but realtime data feed every 1s").
      User nhắc lại rõ hơn (2026-08-18): *"phải chạy chiến thuật từng giây, cho dù tf
      có là 5 phút đi chăng nữa"* — tức là **mọi** khung đều đánh giá lại mỗi giây,
      không phải chỉ khung nhỏ; nến `5m` đang hình thành vẫn được cập nhật và đánh
      giá 300 lần trước khi nó đóng. Đặt tên field sao cho không ai nhầm được.
- [ ] Đăng ký DI trong `binance_bot_module.py` + sanity test
      (`test_backtest_screen_di_sanity.py`) — theo đúng rule "mọi feature ship kèm
      sanity test".

### 3.2. Vòng lặp replay

- [ ] Mỗi tick: cập nhật nến đang hình thành (OHLC chạy) → indicator **tính tạm**
      (`BOT-042`) → strategy đánh giá → có Signal thì `PaperExchange` khớp **tại giá
      tick**.
- [ ] Khi biên giới bar đi qua: **chốt** indicator + `Series.push()` đúng 1 lần cho
      bar vừa đóng. Đây là chỗ dễ sai nhất — sai thì hoặc mất 1 bar, hoặc chốt 2 lần.
- [ ] Equity curve: chốt **theo bar**, không theo tick (nếu không, `equity_curve` sẽ
      to gấp 60× và `BacktestMetrics.max_drawdown` sẽ tính trên tập điểm khác hẳn
      Static → mất khả năng so sánh). Ghi rõ quyết định này vào docstring.
- [ ] Chạy nền qua `IThreadManager` + `CancellationToken` (pattern đã có từ
      `BOT-034`), phát progress event — với 604.800 tick/tuần thì UI **bắt buộc** phải
      huỷ được giữa chừng.

### 3.3. UI

- [ ] Mở khoá lựa chọn tick trong
      [`OrderExecutionMenu.qml`](../../src/presentation/ui/components/OrderExecutionMenu.qml)
      và **nối dây thật** xuống `BackTestViewModel` → command. Đây là phần
      [`BOT-074`](BOT-074_execution_trigger_rule_inverted_lock.md) cố ý **không** làm
      (chưa có consumer); giờ đã có.
- [ ] Test guard của `BOT-074` sẽ vỡ ở bước này — **đúng như thiết kế**. Sửa nó cho
      khớp trạng thái mới, đừng xoá.
- [ ] Hiển thị rõ trên kết quả: đây là Realtime hay Static (kèm độ phân giải tick).
      Hai kết quả trông giống hệt nhau mà ngữ nghĩa khác nhau là bẫy hiểu nhầm.

### 3.4. Test

- [ ] Test "chốt đúng 1 lần/bar": feed N tick trải qua M biên bar → indicator phải đã
      chốt đúng M lần, `Series` dài đúng M.
- [ ] Test tín hiệu giả: 2 tick trong **cùng** 1 bar vượt ngưỡng cross **không được**
      sinh 2 tín hiệu như thể 2 bar (bẫy đã nêu ở `BOT-042` §3 câu 2).
- [ ] Test degenerate: chạy Realtime với độ phân giải tick **bằng đúng** `interval`
      (mỗi bar đúng 1 tick) → kết quả **phải khớp Static**. Đây là cách duy nhất kiểm
      chứng 2 đường code không lệch nhau vì lỗi cài đặt, khi mà nói chung chúng cố ý
      khác nhau (xem §5).

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

- [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md) — **chặn cứng**, không
  có provisional/commit thì không có gì để chạy.
- [`BOT-075`](BOT-075_tick_data_feasibility_spike.md) — **chặn cứng**, có thể đổi
  thiết kế.
- [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅ —
  `PaperExchange`/`BacktestResult` dùng chung.
- [`BOT-074`](BOT-074_execution_trigger_rule_inverted_lock.md) — nên xong trước để UI
  ở trạng thái trung thực trước khi mở khoá.
- [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) — không chặn nhau,
  nhưng SL/TP intra-bar **chỉ chính xác thật** khi có tick → cân nhắc làm task này
  trước.
- [`BOT-077`](BOT-077_calc_on_order_fills.md) — consumer tiếp theo, chặn bởi task này.
