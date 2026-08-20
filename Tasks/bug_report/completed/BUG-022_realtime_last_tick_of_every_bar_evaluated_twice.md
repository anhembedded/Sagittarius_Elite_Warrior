# BUG-022 — Realtime backtest đánh giá tick cuối của **mọi** bar 2 lần; regression test của `BOT-076` không bắt được vì dữ liệu test không giống dữ liệu thật

**Reported:** 2026-08-20, tìm ra khi điều tra loạt WARNING `tick_gap_forced_commit`
trong log user gửi (theo đúng rule CI/CD mới: mọi WARNING phải được điều tra,
không được bỏ qua chỉ vì test vẫn xanh).
**Severity:** 🔴 P1 — sai số kết quả tài chính trên **mọi** lần chạy Realtime,
và làm hỏng chính phép đối chiếu `EPIC-001` đang chuẩn bị.
**Status:** ✅ Đã sửa (2026-08-20) — user chọn sửa luôn dù biết fix sẽ đổi
kết quả mọi backtest Realtime (đổi theo hướng đúng hơn).

## Triệu chứng bề mặt

Log spam WARNING liên tục, mỗi bar 1 dòng, các bar **liền kề nhau** không đứt
quãng:

```
WARNING - action=tick_gap_forced_commit unclosed_bar_start=12:00 next_tick_bar_start=12:15 — committing early, likely missing tick data
WARNING - action=tick_gap_forced_commit unclosed_bar_start=12:15 next_tick_bar_start=12:30 — committing early, likely missing tick data
WARNING - action=tick_gap_forced_commit unclosed_bar_start=12:30 next_tick_bar_start=12:45 — committing early, likely missing tick data
... (mọi bar, không sót bar nào)
```

Chính tính "liền mạch tuyệt đối" này là dấu hiệu: thiếu dữ liệu thật không bao
giờ đều đặn mọi bar như vậy.

## Root cause

Thông báo "likely missing tick data" là **sai** — dữ liệu đầy đủ 100%. Đếm
trực tiếp trong DB runtime, cửa sổ 12:00–14:00 UTC ngày 20/08:
**7,200/7,200 tick 1s = 100%**, không thiếu tick nào.

Nguyên nhân thật nằm ở quy ước `close_time` của Binance so với điều kiện đóng
bar trong `run_realtime_backtest/handler.py`:

```python
if tick.close_time >= bar_end:   # đường đóng bar "bình thường"
```

Nến 1s thật của Binance có `close_time = open_time + 999ms`, tức
`next_open - 1ms` — kiểm chứng trực tiếp trong DB:

```
open=2026-08-20 12:14:59.000000  close=2026-08-20 12:14:59.999000
open=2026-08-20 12:15:00.000000  close=2026-08-20 12:15:00.999000
```

Với bar 15m `[12:00, 12:15)`, tick cuối cùng là 12:14:59 có
`close_time = 12:14:59.999`, còn `bar_end = 12:15:00.000`. Nên
`12:14:59.999 >= 12:15:00.000` là **False** — đường đóng bar bình thường
**không bao giờ chạy**. Bar chỉ được chốt khi tick ĐẦU của bar kế tiếp tới và
rơi vào nhánh `bar_start != forming.bar_start`, tức nhánh cảnh báo "thiếu dữ
liệu".

## Hậu quả thật (không chỉ là log rác)

Vì đường đóng bar bình thường không chạy, tick cuối mỗi bar bị xử lý theo
nhánh **provisional** (`on_forming_bar_tick`) — với OHLC đã bằng đúng nến
đóng cuối cùng — rồi ngay sau đó bar được commit (`on_tick`) với **cùng dữ
liệu đó**. Đây đúng là cú "đánh giá 2 lần cùng 1 state" mà `BOT-076` §3.2 tự
cảnh báo là *"chỗ dễ sai nhất"* và tuyên bố đã chặn.

Đo thực nghiệm (chạy chính handler thật, đếm số lần strategy được gọi):

| Dữ liệu | Số tick | Số lần strategy được gọi |
| :--- | ---: | ---: |
| Synthetic (helper của test hiện tại, `close_time == bar_end`) | 6 | 6 ✅ |
| Thực tế Binance (`close_time == bar_end - 1ms`) | 6 | **9** ❌ |

Thừa đúng 3 lần cho 3 bar — **1 lần thừa mỗi bar**. Tín hiệu có thể khớp lệnh
2 lần, nên số trade/PnL của mọi lần chạy Realtime đều đáng ngờ (lần chạy user
báo: 8 trades, +12.11%).

## Vì sao regression test hiện có không bắt được

`test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close`
được viết đúng ý định, nhưng helper dựng dữ liệu của nó
(`_build_bar_ticks`) đặt `close_time = bar_start + (i+1)*step`, tức tick cuối
có `close_time` **đúng bằng** `bar_end`. Docstring của chính helper còn ghi rõ
điều kiện đó: *"only that the last tick's close_time lands exactly on the bar
boundary"*. Dữ liệu Binance thật không bao giờ thoả điều kiện này. Test vì vậy
xanh vì một lý do không liên quan tới tính chất nó tuyên bố bảo vệ — cùng đúng
loại "false pass" đã gặp ở `BOT-050` (cấu hình mặc định che mất lỗi thật) và
ở test tick-safety của `BOT-110`.

## Fix

**1. Điều kiện đóng bar.** Hằng số mới `_CLOSE_TIME_IS_INCLUSIVE_BY =
timedelta(milliseconds=1)`, điều kiện đổi thành
`tick.close_time + _CLOSE_TIME_IS_INCLUSIVE_BY >= bar_end`. Đây **không phải
epsilon tuỳ tiện**: 1ms chính là độ phân giải mà sàn dùng để phát
`close_time = next_open - 1ms`. Cách này còn đúng cho cả nguồn dữ liệu nào
báo `close_time == bar_end` (vế trái chỉ lớn hơn, vẫn thoả), nên không phá
quy ước nào khác.

**2. `close_time` của nến gộp.** `_FormingBar` thêm field
`last_tick_close_time` (cập nhật trong `absorb()`), và `to_candle()` dùng nó
thay cho `bar_end`. Phát hiện thêm khi test
`test_one_tick_per_bar_matches_static_exactly` fail: nến Realtime gán
`close_time = bar_end` (`00:01:00`) trong khi kline thật Static đọc là
`00:00:59.999` — lệch đúng 1ms, phá chính phép đối soát bit-for-bit mà
`BOT-076` §3.4 yêu cầu. Giờ nến gộp mang đúng ngữ nghĩa kline thật.

## Regression test

Sửa `_build_bar_ticks` dựng `close_time = next_open - 1ms` đúng như dữ liệu
Binance thật (kèm docstring giải thích vì sao, để không ai "sửa lại cho gọn"
về mốc cũ). **Xác nhận fail trước khi sửa** theo `bug-fix-rule.md`: 2 test
fail đúng lý do —
`test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close`
(double-eval) và `test_one_tick_per_bar_matches_static_exactly` (lệch 1ms) —
và log tái hiện đúng loạt WARNING user báo.

Đo lại sau khi sửa, chạy chính handler thật:

| | Trước fix | Sau fix |
| :--- | ---: | ---: |
| 6 tick → số lần gọi strategy | 9 ❌ | **6** ✅ |
| Cảnh báo `tick_gap_forced_commit` giả | 3 | **0** ✅ |

Cảnh báo gap vẫn giữ nguyên cho lỗ hổng dữ liệu **thật** —
`test_a_tick_gap_between_bars_is_logged_and_force_commits_the_stale_bar` vẫn
pass, tức nó chỉ im lặng khi dữ liệu đủ, không phải bị vô hiệu hoá.

## Ghi chú cho `EPIC-001B`

Trước fix, đối chiếu app với TradingView bằng chế độ Realtime sẽ cho lệch
**không phải do chiến lược**. Sau fix thì đường tick đã sạch, nhưng kết quả
Realtime của mọi lần chạy trước ngày 20/08 đều nên coi là không còn giá trị
tham chiếu.
