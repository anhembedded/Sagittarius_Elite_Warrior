# BOLT-001 — Bỏ tính lại biên bar trên mỗi tick trong Historical Tick Backtest

**Nguồn:** chạy `.jules/bolt.prompt.md`
**Ưu tiên:** P2 — không sửa lỗi nào; rút thời gian một vòng chạy đã có thật
**Liên quan:** [`BUG-058`](../bug_report/incomplete/BUG-058_ui_freeze_during_historical_tick_backtest.md) (freeze khi chạy 2.592.000 tick)
**Trạng thái:** ✅ Hoàn thành 2026-08-26
**Báo cáo đo:** [`../reports/BOLT-001_bar_bounds_benchmark.md`](../reports/BOLT-001_bar_bounds_benchmark.md)

## Bottleneck

`RunHistoricalTickBacktestCommandHandler` gọi `_bar_bounds(tick.open_time, interval_seconds)`
**mỗi tick**. Hàm này làm ba việc đắt:

```python
epoch_seconds = tick_open_time.timestamp()                       # đổi múi giờ
bar_start = datetime.fromtimestamp(bar_start_seconds, tz=...)    # dựng datetime
return bar_start, bar_start + timedelta(seconds=interval_seconds)  # dựng datetime nữa
```

Nhưng câu trả lời **chỉ đổi khi sang bar mới**. Với tick 1s trong bar 5 phút,
**299 trên mỗi 300 lần gọi** tính lại đúng giá trị lần trước vừa tính.

## Bản sửa

`_FormingBar` đã giữ sẵn `bar_start` và `bar_end` của bar đang mở. Một phép so
sánh chứa-trong trả lời cùng câu hỏi mà không dựng gì:

```python
if forming is not None and forming.bar_start <= tick.open_time < forming.bar_end:
    forming.absorb(tick)
    bar_end = forming.bar_end
else:
    bar_start, bar_end = _bar_bounds(tick.open_time, interval_seconds)
    ...
```

**Chính xác, không phải xấp xỉ.** `forming.bar_start` do chính `_bar_bounds()`
sinh ra nên đã nằm trên lưới interval, và `bar_end = bar_start + interval`. Làm
tròn xuống bất kỳ thời điểm nào trong cửa sổ nửa mở đó luôn cho đúng
`forming.bar_start`. `interval_seconds` tính một lần ngoài vòng lặp nên lưới
không dịch giữa chừng.

## Đo được

| | ns/tick | 2.592.000 tick |
| :--- | ---: | ---: |
| Trước | 1064 | 2.76 s |
| Sau | 69 | 0.18 s |
| | **15.5×** | **tiết kiệm 2.58 s** |

Đây là thời gian của **riêng bước tính biên bar**, không phải toàn bộ backtest.

## Test

| Test | Bảo vệ gì |
| :--- | :--- |
| `test_the_containment_check_agrees_with_bar_bounds_on_every_tick` | bất biến mà tối ưu dựa vào: chứa-trong và làm-tròn-xuống không bao giờ bất đồng, kiểm trên cả một bar cộng hai biên |
| `test_a_tick_at_exactly_bar_end_starts_a_new_bar_rather_than_joining_the_old` | lỗi off-by-one duy nhất có thể trốn được |

### Test đầu tiên tôi viết là đồ trang trí — ghi lại vì đây là bẫy hay gặp

Bản đầu của test thứ hai kiểm `_bar_bounds()` **trực tiếp**. Nó pass, đọc như
đang bảo vệ tối ưu, và fault injection (`<` → `<=`) **không làm nó đỏ** — vì nó
kiểm code *không đổi*, không kiểm điều kiện mới.

Test gap có sẵn cũng không bắt được: tick nối lại của nó ở bar 2 (T+120s), cách
biên khá xa nên cả hai cách viết đều rẽ cùng nhánh. Bản thay đặt tick nối lại
**đúng vào `bar_end` của bar 0** — thời điểm duy nhất hai cách viết bất đồng.
Sau khi sửa, injection làm **đúng một** test đỏ, đúng test đó.

### Một injection nữa, và vì sao nó đỏ

Tắt hẳn fast path (`if False:`) làm đỏ 2 test. Đó là **kỳ vọng sai của tôi**,
không phải code sai: khi `absorb` chuyển vào nhánh nhanh, nhánh chậm không còn
điều kiện `bar_start != forming.bar_start`, nên tắt fast path không phải "khôi
phục hành vi cũ" mà là ép mọi tick đi đường mở-bar-mới. Nó xác nhận nhánh nhanh
là load-bearing.

## Không làm

Không đụng `PaperExchange`/`BacktestMetrics`/`StrategyEngine` — prompt cấm đúng
lý do: một backtest "nhanh hơn" mà tính ra P&L khác thì tệ hơn một backtest chậm
mà đúng.
