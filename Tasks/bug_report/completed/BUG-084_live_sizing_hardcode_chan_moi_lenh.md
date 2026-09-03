# BUG-084 — Sizing hard-code 20%/1x khiến bot **không đặt nổi một lệnh nào** trên tài khoản có số dư thật

**Reported date:** 2026-09-02
**Severity:** 🟠 **P2** — không crash, không log `ERROR`. Bot chỉ **im lặng không giao dịch**.
**Status:** ✅ **Đã sửa (2026-09-03)** — xem §5.

---

## 1. Hiện tượng (Symptom)

Bật giao dịch, chiến lược phát tín hiệu BUY, và **không có lệnh nào được gửi**. Không traceback,
không dòng `ERROR`, không cảnh báo. `trade-once` báo bị chặn; luồng live thì chỉ có một dòng
`logger.info("Live order blocked: %s", result.blocked_by)`.

Phát hiện khi đối chiếu mockup màn Giao dịch với model dữ liệu thật: mock vẽ số dư
**14 871.60 USDT** và một lệnh **0.002 BTC**, hai con số này không thể cùng tồn tại với cấu hình
đang ship.

## 2. Root cause

`src/application/services/live_trading_coordinator.py:67-68` hard-code sizing của đường live:

```python
_LIVE_SIZING = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0)
_LIVE_LEVERAGE = 1.0
```

20% vốn ở đòn bẩy 1x, đặt cạnh hạn mức `trading.max_notional_per_order_usdt = 500`
(`app_config.json`), cho một cửa sổ dùng được **rất hẹp** — và số dư mặc định của một tài khoản
Futures Testnet (15 000 USDT) nằm **ngoài** cửa sổ đó.

Đo thật bằng chính `calculate_live_order_quantity()`, giá tham chiếu 64 105.35, `step_size` 0.001,
`minNotional` 100:

| Số dư USDT | Khối lượng | Notional | Kết quả |
| ---: | ---: | ---: | :--- |
| **14 871.60** *(số mock vẽ)* | 0.046 | **2 948.85** | ❌ chặn — vượt hạn mức 500 |
| 15 000 *(mặc định testnet)* | 0.046 | 2 948.85 | ❌ chặn — vượt hạn mức 500 |
| 2 500 | 0.007 | 448.74 | ✅ qua |
| 1 000 | 0.003 | 192.32 | ✅ qua |
| 160 | 0.000 | 0.00 | ❌ chặn — dưới `minNotional` |

Cửa sổ dùng được chỉ khoảng **500 – 2 500 USDT**. Ngoài khoảng đó, bot không giao dịch, và
**không nói vì sao** ở nơi người vận hành nhìn.

Đây cũng là lý do bài test tích hợp `EPIC-021G` phải stub số dư xuống 1 000 — nếu chạy với số dư
15 000 của fake server thì mọi test sẽ dừng ở hạn mức trước khi chạm hành vi cần kiểm
(`test_live_trading_pipeline_against_fake_server.py`, docstring đã ghi lý do).

## 3. Vì sao nó im lặng — nửa thứ hai của bug

`ExecuteOrderCommandHandler` trả `ExecuteOrderResult(blocked_by=MAX_NOTIONAL_PER_ORDER, ...)`,
và `LiveTradingCoordinator.handle()` ghi đúng một dòng `INFO`. Không có gì nổi lên UI, không có
gì phân biệt *"chiến lược không phát tín hiệu"* với *"phát tín hiệu nhưng bị chặn"*. Với người
vận hành, hai trường hợp đó **trông giống hệt nhau**: màn hình đứng im.

## 4. Suggested next steps

1. **Không sửa bằng cách nới hạn mức.** 500 USDT/lệnh là con số an toàn user đã chốt
   (`EPIC-021G` §2.2); nó không phải thứ bị sai ở đây.
2. **Sizing phải thành control thật**, đúng như `EPIC-021G` §6.7 đã dự liệu (*"control UI thật
   thuộc `EPIC-021I`"*) — xem [`EPIC-021I`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021I_man_giao_dich_moi.md)
   §3.3 điểm 1. Trước khi có UI, tối thiểu là 2 config key (`trading.live_sizing_percent`,
   `trading.live_leverage`) để không phải sửa code mới đổi được.
3. **Lý do bị chặn phải nhìn thấy được** — `EPIC-021I` §3.3 điểm 12. Một lệnh bị hạn mức chặn là
   sự kiện một-lần-có-nghĩa, đúng tiêu chí `INFO` mà `EPIC-021G` §2.5 đặt ra, và phải hiện trên
   màn chứ không chỉ trong log.
4. **Regression test viết trước:** với số dư 15 000 và hạn mức 500, một tín hiệu BUY phải cho
   `blocked_by == MAX_NOTIONAL_PER_ORDER` **và** không có lệnh nào tới sàn — hạ tầng đã sẵn ở
   `tests/integration/application/test_live_trading_pipeline_against_fake_server.py`.

## 5. Đóng thế nào (2026-09-03)

Đi đúng cả 3 hướng của §4, không né hướng nào:

**1. Sizing thành control thật (§4 điểm 2).** Hai `ConfigKeys` mới —
`TRADING_LIVE_SIZING_PERCENT` (`trading.live_sizing_percent`) và `TRADING_LIVE_LEVERAGE`
(`trading.live_leverage`) — mặc định `20.0`/`1.0` trong `app_config.json` (giữ nguyên đúng con số
hard-code cũ, để hành vi mặc định không đổi âm thầm; đây là bug "không cấu hình được", không phải
"số 20% sai"). `LiveTradingCoordinator` không còn giữ `_LIVE_SIZING`/`_LIVE_LEVERAGE` cấp module —
constructor nhận `sizing_percent`/`leverage` tường minh, `binance_bot_module.py::boot()` đọc 2 key
này từ `IConfig` và truyền vào lúc dựng coordinator, cạnh `live_symbol`/`live_strategy_key`/
`live_interval` đã có. Đổi hạn mức 500 USDT không đụng tới — đúng như §4 điểm 1 dặn.

**2. Lý do bị chặn phải nhìn thấy được (§4 điểm 3).** Domain event mới
`LiveOrderBlockedEvent(symbol, reason)` (`domain/events/live_order_blocked_event.py`) — publish qua
`IEventPublisher` (constructor param mới của coordinator) ở cả hai điểm từng chỉ log:
- Khối lượng tính ra bằng 0 (số dư quá thấp so với mức sizing) — trước đây `logger.debug()`, vô
  hình hoàn toàn.
- `ExecuteOrderResult.blocked` sau khi dispatch (hạn mức/safety gate/minNotional chặn) — trước đây
  `logger.info()`, không tới màn hình nào.

`OrderFeed` (đã có `orderFilled`/`positionChanged`/`positionClosed`, `EPIC-021H`/`BUG-086`) thêm
signal thứ tư `orderBlocked`, đúng tiền lệ "một Feed, nhiều sự thật cùng miền" thay vì tạo Feed thứ
năm. `TradingPresenter._on_order_blocked()` (mới) ghi vào `log_model` của chính màn Giao dịch —
`level="info"` có chủ đích: `LogListModel` chỉ định nghĩa icon cho `info`/`error`/`success`, và một
lệnh bị chặn đúng như thiết kế **không phải** lỗi ứng dụng — dùng `error` sẽ mô tả sai một safety
gate đang làm đúng việc của nó thành một trục trặc. Đúng tiêu chí INFO "sự kiện một-lần-có-nghĩa"
mà `EPIC-021G` §2.5 đã đặt ra.

**3. Regression test.** Không tái dùng nguyên bộ hạ tầng
`test_live_trading_pipeline_against_fake_server.py` cho case cụ thể của bug này (test đó đã có sẵn
comment giải thích *vì sao* nó phải stub số dư xuống 1 000 — đúng root cause bug này, không phải
việc cần thêm case) — thay vào đó:
- `tests/unit/application/services/test_live_trading_coordinator.py`:
  `test_sizing_percent_and_leverage_are_config_driven_not_hardcoded` (hai coordinator, hai
  `sizing_percent` khác nhau, cùng balance/giá, phải cho ra khối lượng lệnh khác nhau — chứng minh
  không còn hard-code), `test_a_blocked_order_publishes_a_live_order_blocked_event`,
  `test_an_accepted_order_does_not_publish_a_blocked_event`,
  `test_a_zero_computed_quantity_publishes_a_live_order_blocked_event`.
- `tests/unit/presentation/ui/common/test_order_feed.py`:
  `test_live_order_blocked_event_reaches_every_listener`, `test_stop_unsubscribes_all_four`
  (mở rộng từ `..._all_three`).
- `tests/unit/presentation/ui/screens/trading/test_trading_presenter_toggle.py`:
  `test_order_blocked_appears_in_the_screens_own_log_panel` — xác nhận đúng nội dung
  (symbol + reason) và đúng level xuất hiện trong `log_model` thật của `TradingViewModel`, không
  mock.

Xác nhận đỏ trước fix bằng `git stash` (3 file production), đúng lý do dự kiến ở từng test
(`TypeError: takes 5 positional arguments but 8 were given` cho constructor mới,
`AttributeError: 'OrderFeed' object has no attribute 'orderBlocked'`,
`AttributeError: 'TradingPresenter' object has no attribute '_on_order_blocked'`), xanh sau khi
khôi phục fix. `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` xanh toàn bộ sau khi gộp thay
đổi này.
