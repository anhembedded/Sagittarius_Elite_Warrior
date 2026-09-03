# BUG-085 — Đường live không lọc theo khung thời gian: hai interval cùng symbol làm hỏng state chỉ báo

**Reported date:** 2026-09-02
**Fixed date:** 2026-09-03
**Severity:** 🟠 **P2** — sinh **tín hiệu sai**, không sinh lỗi. Trên testnet là tiền giả; cùng
đoạn code này sau chạy tiền thật.
**Status:** ✅ Fixed — xem §5.

---

## 1. Hiện tượng (Symptom)

Chưa quan sát thấy trên máy user — phát hiện khi đối chiếu mockup màn Giao dịch (header ghi
`1m`) với đường xử lý tick thật, và thấy **không có chỗ nào trong luồng live biết tới khung thời
gian**.

## 2. Root cause

`src/application/event_handlers/market_data/market_tick_event_handler.py`, thân `handle()`:

```python
if self._strategy_engine is None or md.symbol != self._live_symbol:
    return
signal = self._strategy_engine.on_tick(md)
```

Lọc **duy nhất** theo `md.symbol`. `MarketData` **có** field `interval`
(`src/domain/entities/market_data.py:12`) và nó bị bỏ qua hoàn toàn.

`ConfigKeys` cũng không có key nào cho khung thời gian của đường live — chỉ có
`TRADING_LIVE_SYMBOL` và `TRADING_LIVE_STRATEGY_KEY`.

Hệ quả: nếu live stream đang chạy nhiều hơn một interval cho **cùng một symbol** (Dev Board mở
`BTCUSDT@1m`, màn khác mở `BTCUSDT@5m`), **cả hai** dòng nến cùng đổ vào **một**
`StrategyEngine`. Mỗi chỉ báo trong engine giữ state tăng dần theo từng nến (`BOT-042B/C`) — một
EMA được nạp xen kẽ nến 1m và nến 5m **không phải EMA của khung nào cả**. Tín hiệu sinh ra từ
state đó là tín hiệu sai, và nó dẫn thẳng tới `LiveTradingCoordinator` → lệnh thật.

**Class này đã tự cảnh báo đúng cơ chế đó — nhưng chỉ cho symbol**, không cho interval. Trích
docstring của chính nó:

> *"Every indicator inside `strategy_engine` holds mutable, incrementally built state […] mixing
> symbols would corrupt that state — an EMA fed alternating BTCUSDT and ETHUSDT closes is neither
> symbol's EMA."*

Đổi "symbols" thành "intervals" thì câu đó vẫn đúng nguyên vẹn, và **không** có dòng code nào
chặn nó.

## 3. Vì sao chưa nổ

`trading.live_strategy_key` mặc định **rỗng** ⇒ `binance_bot_module.py` không dựng
`StrategyEngine` ⇒ `MarketTickEventHandler` vẫn là logger trơ. Bug chỉ sống dậy đúng lúc có người
cấu hình live strategy — tức đúng lúc `EPIC-021I` cho phép chọn chiến lược trên UI.

## 4. Suggested next steps

1. Thêm khung thời gian vào cấu hình đường live (`trading.live_interval`), và **lọc**:
   `md.interval != self._live_interval → return`, ngay cạnh bộ lọc symbol đã có.
2. Cấu hình rỗng phải là *"chưa cấu hình live"*, đối xứng với cách `live_strategy_key` rỗng đang
   xử lý — **không** mặc định một interval nào đó, vì đoán sai khung là đoán sai chiến lược.
3. **Regression test viết trước**, unit thuần, không cần mạng: nạp xen kẽ `1m` và `5m` cùng
   symbol vào handler → engine chỉ được nhận đúng các nến `1m`. Test này phải **đỏ** trước khi
   sửa.
4. UI chọn khung thời gian: [`EPIC-021I`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021I_man_giao_dich_moi.md)
   §3.3 điểm 4. `TimeframePicker` dùng chung đã tồn tại (`EPIC-015` Phase 1) — không phải viết mới.

## 5. Fix (2026-09-03)

Đúng theo §4 gợi ý ban đầu, không mở rộng phạm vi:

1. `ConfigKeys.TRADING_LIVE_INTERVAL` (`trading.live_interval`) mới, mặc định `""` trong
   `app_config.json` — đối xứng với `TRADING_LIVE_STRATEGY_KEY`. Rỗng nghĩa là **"chưa cấu hình
   live interval"**, không đoán một khung nào cả.
2. `MarketTickEventHandler.__init__` nhận thêm `live_interval: str`; `handle()` lọc thêm
   `md.interval != self._live_interval → return`, đặt cạnh bộ lọc `md.symbol` đã có
   (`market_tick_event_handler.py`).
3. `binance_bot_module.py::boot()` chỉ dựng `StrategyEngine`/`LiveTradingCoordinator` khi **cả
   ba** `live_symbol`, `live_strategy_key`, `live_interval` đều được cấu hình — nếu thiếu bất kỳ
   cái nào, `MarketTickEventHandler` vẫn là logger trơ như cũ (đối xứng với hành vi gốc cho
   `live_strategy_key`).
4. UI chọn khung thời gian cho đường live (nối `TimeframePicker` vào `TRADING_LIVE_INTERVAL`) —
   **để ngoài phạm vi** bug này, thuộc `EPIC-021I` §3.3 điểm 4 như §4.4 đã ghi; bug này chỉ đóng
   phần **thực thi/an toàn** (engine không còn nhận nhầm khung).

## 6. Regression test (viết trước, xác nhận đỏ đúng lý do trước khi sửa)

`tests/unit/application/event_handlers/test_market_tick_event_handler.py`:

- `test_ignores_a_tick_for_a_different_interval_same_symbol` — cùng symbol, khác interval → bị
  chặn.
- `test_feeds_only_the_configured_interval_when_intervals_are_interleaved` — nạp xen kẽ `1m`/`5m`
  cùng symbol → engine chỉ nhận đúng 2 nến `1m`, không nhận nến `5m` nào.
- `test_no_live_interval_configured_ignores_every_tick` — interval rỗng chặn **mọi** tick, không
  fallback về khung nào.

Cả ba **fail** trước khi sửa `handle()` (do `TypeError: __init__() missing 1 required positional
argument: 'live_interval'`, sau khi tham số được thêm vào lời gọi test, rồi `AssertionError` đúng
vì `handle()` chưa lọc theo interval); **pass** sau khi sửa. Toàn bộ 9 test trong file (bao gồm 6
test cũ, đã cập nhật để truyền `live_interval`) đều xanh:
`PYTHONPATH=/home/user QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
tests/unit/application/event_handlers/test_market_tick_event_handler.py -q` → `9 passed`.

`mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts` →
`Success: no issues found in 243 source files`.
