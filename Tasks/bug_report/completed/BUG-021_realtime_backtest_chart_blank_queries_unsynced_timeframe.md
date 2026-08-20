# BUG-021 — Chart trắng hoàn toàn sau mỗi lần chạy Realtime backtest (query nến `timeframe` chưa từng được sync)

**Reported:** 2026-08-20, user gửi log 1 lần chạy Realtime backtest thành công
(8 trades, +12.11%) nhưng chart không vẽ gì cả.
**Severity:** 🔴 P1 — hỏng hoàn toàn phần hiển thị của **mọi** lần chạy chế độ
Realtime, không phải ca hiếm.
**Status:** ✅ Đã sửa (2026-08-20), có regression test mutation-verified.

## Symptom

Log kết thúc backtest bình thường:

```
REALTIME_BACKTEST_TRACE action=handler_simulation_complete ticks=604800 bars_committed=673
REALTIME_BACKTEST_TRACE action=handler_complete trades=8 net_profit_percent=12.10
Realtime backtest complete for BTCUSDT: 8 trades, net profit 12.11%
BACKTEST_TRACE action=query_execute_start symbol='BTCUSDT' timeframe='15m' ... 
BACKTEST_TRACE action=query_execute_complete symbol='BTCUSDT' rows=0
```

Backtest chạy đúng, ra 8 lệnh thật — nhưng `rows=0` ở bước lấy nến vẽ chart,
nên chart trắng: không nến, không đường EMA, không marker.

## Root cause

Kiểm chứng bằng DB runtime thật
(`Sagittarius_Elite_Warrior/Sagittarius_Elite_Warrior/database/BTCUSDT.db`):

| Interval | Số nến |
| :--- | ---: |
| 1s | 2,686,198 |
| 1m | 54,863 |
| 5m | 2,017 |
| 1d | 366 |
| 1h | 168 |
| **15m** | **0** |

Một lần chạy Realtime **chỉ** sync/coverage-check `tick_resolution` (1s) —
đúng theo thiết kế, có ghi rõ trong `BackTestPresenter._effective_data_interval()`:
kiểm tra `config.timeframe` cho Realtime là sai, vì Realtime đánh giá theo
tick chứ không theo `timeframe`. Nhưng `_fetch_and_emit_chart_data()` lại đi
query `GetHistoricalKlinesQuery(interval=config.timeframe.value)` để vẽ —
tức hỏi một interval chưa bao giờ được đồng bộ. Không có nến 15m nào trong
DB → `rows=0` → chart trắng.

## Vì sao không sửa bằng cách "sync thêm nến 15m"

Đây là hướng sửa đầu tiên được đề xuất và **user bác đúng**: *"sao phải query
db 15m? -> không phải gộp các 1s thành 15m sao? tui kì vọng là thế, dùng db
15m để vẽ liệu có chính xác?"*

Không chính xác. Engine Realtime **đã tự gộp** tick 1s thành nến `interval`
rồi (`_FormingBar.absorb()` → `_commit_bar()`, log `bars_committed=673`) —
những nến đó mới là nến chiến lược thật sự nhìn thấy. Nến 15m chính thức của
sàn là **một chuỗi khác**: đầy đủ, trong khi nến engine tự gộp mang đúng
những lỗ hổng tick nó gặp phải. Vẽ nến đầy đủ ở dưới, gắn marker tính từ nến
có lỗ hổng ở trên → chart mâu thuẫn với quyết định thật của chiến lược, đúng
loại lỗi `EPIC-001` sinh ra để bắt.

## Fix

`BacktestResult` thêm field tuỳ chọn `committed_bars: list[MarketData] | None
= None` (additive — Static để `None`, mọi construction cũ không phải sửa).
`RunRealtimeBacktestCommandHandler` giữ lại từng `closed_candle` nó commit và
trả ra qua field này (tiện thể bỏ biến đếm `bars_committed` giờ trùng lặp với
`len(committed_bars)`). `BackTestPresenter._fetch_and_emit_chart_data()` ưu
tiên `result.committed_bars` khi có, chỉ query DB khi `None` (đường Static,
giữ nguyên 100%).

## Regression test

`test_realtime_run_draws_its_own_committed_bars_not_a_fresh_kline_query` —
dựng đúng điều kiện thật: Realtime run + `GetHistoricalKlinesQuery` trả `[]`.
`test_static_run_still_queries_klines_when_no_committed_bars` giữ đường Static
không bị vạ lây.

**Mutation-verified**: tắt fix (`if False and result.committed_bars:`) →
test fail đúng lý do — `render_historical_data` được gọi **0 lần**, tức chart
trắng, khớp chính xác triệu chứng user báo. Khôi phục → 174 test pass.
