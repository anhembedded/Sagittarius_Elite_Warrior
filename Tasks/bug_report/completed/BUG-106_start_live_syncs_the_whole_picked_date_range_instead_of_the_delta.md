# BUG-106 — "Start Live" syncs the whole picked Data Range from the exchange instead of just the missing delta

**Reported date:** 2026-09-03
**Fixed date:** 2026-09-03
**Severity:** 🟡 P2 — no crash, no data loss, but Dev Board's "Start Live" can hang for minutes doing
a real network backfill of hundreds of thousands of candles the user never asked for, and the chart
shows a single stale/malformed candle the whole time it's stuck.
**Status:** ✅ Fixed — see §3.

---

## 1. Hiện tượng (Symptom)

User gửi screenshot Dev Board thật + log: bấm "Start Live" (ETHUSDT), thanh tiến độ hiện *"Đang
đồng bộ ETHUSDT 1s (246,000/604,800 nến)"* — vẫn đang chạy nhiều phút sau, và chart chỉ hiện **1
cây nến** méo mó (trục giá/khối lượng lẫn lộn) thay vì tải sẵn ~1000 cây nến như user biết Dev
Board vẫn làm. Câu hỏi trực tiếp: *"dev board có thực toán real time là tải 1000 cây nến trước mà,
sao nó lại đồng bộ nhiều thế"*.

`604,800` khớp chính xác với 7 ngày × 86400 giây (khung `1s`) — đúng bằng `DEFAULT_LOOKBACK_DAYS`
(`dashboard_view_model.py`) nhân với số giây/ngày ở interval `1s` mà tài khoản này đang để làm mặc
định (`ConfigKeys.DEFAULT_INTERVAL`, đã xác nhận từ log phiên trước trong cùng session).

## 2. Root cause

`StreamLifecycleController._on_start_stream()` đọc `start_time`/`end_time` từ ô "Data Range" (mục
đích ban đầu: giới hạn *hiển thị* — dùng cho `_run_load_history()`, một truy vấn DB local rẻ) rồi
truyền **y hệt** giá trị đó vào `_run_sync_and_start()` → `_sync_market_data()` →
`SyncMarketDataCommand(start_time=..., end_time=...)` — bước **đồng bộ mạng thật** từ Binance.

`SyncMarketDataCommandHandler._determine_start_time()` đã có sẵn đúng cơ chế cho tình huống "Start
Live": nếu `command.start_time` là `None`, nó tự tính từ `get_latest_kline_time()` — chỉ đồng bộ
phần **chênh lệch** từ nến local mới nhất tới hiện tại, rẻ và nhanh. Nhưng vì
`_run_sync_and_start()` luôn truyền `start_time`/`end_time` tường minh (khác `None`), nhánh đó
không bao giờ được dùng cho luồng Start Live — mọi lần bấm đều đồng bộ lại **toàn bộ** khoảng đã
chọn trên Data Range, bất kể local đã có sẵn phần lớn dữ liệu đó hay chưa.

Khoảng Data Range mặc định (`DEFAULT_LOOKBACK_DAYS = 7`) không co giãn theo interval — hợp lý với
`1h`/`1d` (168/7 nến) nhưng đồng bộ hoá **604,800 nến** khi interval mặc định của tài khoản này là
`1s`. Chart chỉ hiện 1 nến méo trong lúc đó là hệ quả trực tiếp: `_run_load_history()` (bước vẽ
chart) chỉ chạy **sau khi** bước sync mạng hoàn tất — nến hiện tại là dữ liệu còn sót từ lần chạy
trước, chưa được thay thế.

## 3. Fix

Tách rõ hai mục đích của cùng một cặp `start_time`/`end_time`:

- `_run_sync_and_start()` không còn truyền `start_time`/`end_time` của Data Range vào bước
  `_sync_market_data()` nữa — luôn gọi với `None, None`, để `SyncMarketDataCommandHandler` tự làm
  đúng việc nó đã có sẵn: đồng bộ **chênh lệch** từ nến local mới nhất, hoặc `days_back_if_empty`
  (mặc định 30 ngày) nếu symbol chưa có dữ liệu local nào.
- `_run_load_history()` (bước đọc DB local để vẽ chart) **giữ nguyên** — vẫn dùng đúng
  `start_time`/`end_time`/`limit` user đã chọn, vì đây là truy vấn cục bộ, rẻ, không có lý do gì để
  bó hẹp.

Không đụng tới `DEFAULT_LOOKBACK_DAYS`/`days_back_if_empty` — cả hai vẫn dùng đúng chỗ của chúng
(seed mặc định cho form, và fallback khi symbol hoàn toàn chưa có dữ liệu), không phải root cause
của báo cáo này.

## 4. Regression test (viết trước, xác nhận đỏ đúng lý do trước khi sửa)

`tests/unit/presentation/ui/screens/test_dashboard_presenter.py`:

- `test_run_sync_and_start_never_forwards_the_date_range_to_the_sync_command` — gọi
  `_run_sync_and_start` với `start`/`end` cụ thể, assert `SyncMarketDataCommand.start_time`/
  `end_time` đều là `None`.
- `test_run_sync_and_start_still_loads_history_for_the_picked_date_range` — cùng lời gọi, assert
  `GetHistoricalKlinesQuery.start_time`/`end_time` vẫn đúng bằng giá trị user chọn — chứng minh chỉ
  bước sync mạng bị bó hẹp, không phải toàn bộ luồng.

Trước khi sửa: **đỏ đúng lý do** —
`AssertionError: assert datetime.datetime(2024, 1, 1, ...) is None`. Sau khi sửa: cả hai xanh.

`tests/unit/presentation/ui/screens/test_dashboard_presenter.py` (77 test), +
`tests/unit/presentation/ui/screens/dashboard/` + `tests/integration/presentation/ui/
test_dashboard_integration.py` + `test_dashboard_live_stream.py` + `test_dev_board_known_gaps.py` +
`test_dev_board_async_race_conditions.py`: **107/107 xanh**.
`mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts` →
`Success: no issues found in 245 source files`.
