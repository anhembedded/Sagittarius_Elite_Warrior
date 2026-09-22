# Nhiệm vụ: `calc_on_order_fills` — chạy lại strategy ngay khoảnh khắc lệnh khớp

**Trạng thái:** ✅ Done (2026-09-22)

> Thuộc Epic [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md).
> **Chặn bởi** [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md).
>
> Làm rõ dòng *"Execution Trigger Rules — **On order filled** — ❓ chưa rõ nghĩa
> trong ngữ cảnh backtest"* ở [`BOT-040`](BOT-040_backtest_screen_full_feature_epic.md)
> §2.1. User đã giải thích: đây chính là `calc_on_order_fills = true` của Pine Script.
>
> ⚠️ **Đọc §2 trước khi ưu tiên task này.** Nó **không phải** thứ giải quyết vấn đề an
> toàn mà user lo — dễ làm nhầm thứ tự.

## 1. Ngữ nghĩa (user đã làm rõ)

Mặc định, script chỉ chạy lại khi nến đóng. Nếu lệnh khớp ở phút thứ 10 của nến 1H,
phải chờ tới phút 60 script mới chạy lần nữa. `calc_on_order_fills = true` thêm **một
lần chạy nữa ngay tại khoảnh khắc khớp lệnh**.

Hiện trạng đã verify trong [`run_static_backtest/handler.py`](../../src/application/use_cases/backtest/run_static_backtest/handler.py):

| Thời điểm | Việc xảy ra |
| :--- | :--- |
| Đóng nến N | `on_tick(nến N)` → Signal → `pending_signal` |
| **Open nến N+1** | **`exchange.fill(...)` — khớp tại đây** |
| Suốt nến N+1 | **Không có gì chạy** |
| Đóng nến N+1 | `on_tick(nến N+1)` |

→ Khoảng trống đúng **trọn một cây nến**. Khớp chính xác hành vi **mặc định** của Pine
(`calc_on_order_fills = false`) — không phải làm sai, mà là **chưa có tuỳ chọn**.

## 2. ⚠️ Task này KHÔNG phải cách giải quyết nỗi lo Stop Loss

User nêu kịch bản: *"lệnh khớp phút 10, phải chờ tới phút 60 mới đặt được Stop Loss —
trễ 50 phút có thể cháy tài khoản."*

**Cách giải quyết đúng không phải task này, mà là
[`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md).**

Pine **buộc phải** có `calc_on_order_fills` vì trong Pine, muốn đặt SL thì phải gọi
`strategy.exit()` **từ trong script** → script không chạy thì không đặt được. Đó là
**giới hạn của Pine**, không phải quy luật tự nhiên.

Sàn thật (Binance) không vậy: SL/TP là **lệnh nằm sẵn trên sàn** (bracket/OCO), đặt
kèm ngay lúc vào lệnh, sàn tự canh 24/7 — bot không cần chạy lại lần nào, bot sập
nguồn thì SL vẫn còn. `BOT-041` đã định hướng đúng mô hình này (*"SL/TP tự đóng vị
thế, kiểm tra bằng `high`/`low` mỗi bar"*).

→ Nếu SL/TP là **thuộc tính của vị thế** do `PaperExchange` tự canh, kịch bản "cháy
tài khoản vì trễ 50 phút" **không thể xảy ra**, kể cả khi vĩnh viễn không làm task
này.

**Hệ quả về ưu tiên**: `BOT-041` ≫ task này. Đừng làm task này *để* giải quyết an
toàn SL — sẽ tốn công mà vẫn không đóng được đúng lỗ hổng.

## 3. Vậy task này còn cần cho gì?

Cho các quyết định **thật sự đòi hỏi logic strategy** sau khi biết giá khớp *thực tế*
(mà `BOT-041` không thay được):

- **Pyramiding** — vào lệnh 1 xong, tính khối lượng lệnh 2 dựa trên giá khớp thật.
- **Đảo chiều tức thì** trong cùng nến, không chờ hết nến.
- **SL động theo giá khớp thật** — khác giá dự kiến do slippage, nên phải tính lại
  chứ không đặt trước được.

## 4. Vì sao chặn bởi `BOT-076`

Với **chỉ dữ liệu nến** (chưa có tick), `calc_on_order_fills` là **trường hợp suy
biến**: fill xảy ra ở open nến N+1, mà nến đó lúc mới mở có `open = high = low =
close` → indicator tính lại chỉ phản ánh mỗi giá open, gần như không mang thêm thông
tin.

Nó **chỉ thực sự có nghĩa khi đã có tick data** — lúc đó "khoảnh khắc khớp lệnh" là
một điểm có thật giữa lòng nến, với trạng thái indicator có thật tại điểm đó.

Đây chính là lý do `BOT-040` §2.1 từng ghi lựa chọn này là *"chưa rõ nghĩa trong ngữ
cảnh backtest"* — nhận định đó **đúng** với hoàn cảnh lúc bấy giờ (chưa có tick).

## 5. Các bước thực hiện

- [x] Thêm cờ vào `RunHistoricalTickBacktestCommand` (mặc định **tắt** — giữ nguyên
      hành vi `BOT-076` ship ra). (`RunRealtimeBacktestCommand` trong task gốc đã đổi
      tên thành `RunHistoricalTickBacktestCommand` từ trước — xác nhận lại trước khi
      sửa, đúng thói quen "đo lại trước khi làm" của repo này.)
- [x] Trong vòng lặp tick: sau khi `PaperExchange` khớp một lệnh, chạy thêm **đúng
      một** lượt đánh giá strategy tại chính tick đó, **trước** khi sang tick kế tiếp.
- [x] **Chặn đệ quy vô hạn**: lượt chạy thêm này có thể lại sinh Signal → lại khớp →
      lại chạy thêm. Phải có giới hạn cứng số lần lặp trong 1 tick (Pine cũng giới
      hạn) + test cho kịch bản strategy luôn sinh Signal.
- [x] `Series`/indicator **không được chốt** trong lượt chạy thêm — vẫn là cùng một
      bar, chốt ở đây sẽ đẩy sai lịch sử (đúng lớp lỗi `BOT-042` §3 câu 2 đã cảnh
      báo).
- [x] Mở khoá + nối dây lựa chọn "Khi lệnh được khớp" — `OrderExecutionMenu.qml`
      không còn tồn tại (QML đã gỡ trước `EPIC-025`); nối dây thật trong
      `order_execution_dialog.py` (QtWidgets, `ChecklistOverlay`) thay vào đó.
- [x] Test: bật cờ → strategy được gọi thêm đúng 1 lần ngay sau fill, tại đúng giá
      tick đó; tắt cờ → số lần gọi không đổi so với `BOT-076`.

## 6. Rủi ro / Lưu ý

- **Đệ quy** là rủi ro thật, không lý thuyết: entry → fill → chạy lại → entry tiếp.
  Giới hạn cứng + test là bắt buộc, không phải "nếu có thời gian".
- Bật cờ này làm kết quả **khác đi** so với cùng cấu hình lúc tắt — đó là bản chất
  tính năng, nhưng phải hiện rõ trên UI/kết quả là cờ đang bật, kẻo so sánh nhầm 2 lần
  chạy tưởng cùng điều kiện.
- Task này **không** đụng chế độ Static — Static giữ nguyên hành vi Pine mặc định.

## 7. Phụ thuộc

- [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md) — **chặn cứng** (xem §4).
- [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md) — không chặn nhau,
  nhưng **ưu tiên cao hơn hẳn** (xem §2).
- [`BOT-040`](BOT-040_backtest_screen_full_feature_epic.md) §2.1 — dòng "On order
  filled", nay đã rõ nghĩa.

## Implementation notes (2026-09-22)

- **Domain/Application**: `RunHistoricalTickBacktestCommand.calc_on_order_fills: bool = False`
  (`application/run_historical_tick_backtest/command.py`). `RunHistoricalTickBacktestCommandHandler._reevaluate_on_order_fill()`
  (`handler.py`) chạy thêm strategy tại đúng tick vừa khớp lệnh, dùng `on_forming_bar_tick(..., is_closed=False)` nên
  Series/indicator không bị chốt sai. Giới hạn cứng `_MAX_ORDER_FILL_REEVALUATIONS = 10` — vượt giới hạn thì dừng và ghi
  `logger.warning(...calc_on_order_fills_cap_reached...)`, không âm thầm cắt.
- **UI thật (không phải QML)**: `OrderExecutionMenu.qml` không còn tồn tại — QML đã gỡ khỏi codebase trước `EPIC-025`.
  Mở khoá dòng "On order fill" (index 1) trong `order_execution_dialog.py` (`ChecklistOverlay`, QtWidgets thật), nối qua
  `BackTestViewModel.calcOnOrderFills` (Property mới) → `BacktestRunConfig.calc_on_order_fills` (qua
  `run_config_builder.py`, cả `build_run_config` lẫn `snapshot_current_config`) → `RunHistoricalTickBacktestCommand`
  (qua `execution_coordinator.py`). `compute_diff_summary()` báo thay đổi cờ này khi và chỉ khi đang ở chế độ
  Historical Tick — vô nghĩa ở Static/Bar Close nên không báo nhầm.
- **9 test mới**: 3 ở tầng handler (tắt cờ giữ nguyên số lần gọi `BOT-076`; bật cờ chạy thêm đúng 1 lần; strategy luôn
  sinh Signal thì dừng đúng ở giới hạn cứng, mutation-verify bằng cách hạ giới hạn xuống 3 và xác nhận test đỏ đúng lý
  do), 2 ở `run_config_builder`, 2 ở `backtest_fsm_matrix` (báo/không báo diff tuỳ chế độ), 1 ở `execution_coordinator`
  (cờ được chuyển đúng cả hai chiều vào command), và cập nhật `test_order_execution_modal.py` — file này tự dự đoán
  trước "nếu unlock dòng 1, test này phải đỏ lại 'by design'", và đúng như vậy khi chạy trước khi sửa; đã cập nhật
  `_EXPECTED_LOCK_STATE` + thêm 2 test tương tác mới cho dòng này. Toàn bộ 690 test của module `backtesting` xanh;
  `ruff`/`mypy` sạch (3 file UI đã nằm sẵn trong danh sách "frozen debt" `@Property` false-positive của
  `pyproject.toml`, không phải nợ mới).
