# BUG-085 — Đường live không lọc theo khung thời gian: hai interval cùng symbol làm hỏng state chỉ báo

**Reported date:** 2026-09-02
**Severity:** 🟠 **P2** — sinh **tín hiệu sai**, không sinh lỗi. Trên testnet là tiền giả; cùng
đoạn code này sau chạy tiền thật.
**Status:** 🔴 Open — root cause đọc được thẳng từ code (§2), chưa có repro sống.

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
4. UI chọn khung thời gian: [`EPIC-021I`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021I_man_giao_dich_moi.md)
   §3.3 điểm 4. `TimeframePicker` dùng chung đã tồn tại (`EPIC-015` Phase 1) — không phải viết mới.
