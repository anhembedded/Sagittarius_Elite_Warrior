# BUG-084 — Sizing hard-code 20%/1x khiến bot **không đặt nổi một lệnh nào** trên tài khoản có số dư thật

**Reported date:** 2026-09-02
**Severity:** 🟠 **P2** — không crash, không log `ERROR`. Bot chỉ **im lặng không giao dịch**.
**Status:** 🔴 Open — root cause **đã xác nhận bằng chạy thật** (§3), hướng sửa gắn với
[`EPIC-021I`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021I_man_giao_dich_moi.md) §3.3 điểm 1.

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
