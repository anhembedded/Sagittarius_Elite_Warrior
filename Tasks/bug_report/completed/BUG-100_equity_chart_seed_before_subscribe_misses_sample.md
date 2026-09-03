# BUG-100 — Biểu đồ equity đọc dữ liệu seed trước khi subscribe `EquityFeed` — mẫu ghi đúng lúc đó bị mất, không xuất hiện cho tới lần mở màn kế tiếp

**Reported date:** 2026-09-03
**Severity:** 🟡 P2 — mất một điểm dữ liệu equity hiếm khi trùng đúng cửa sổ hẹp lúc dựng màn hình
Giao dịch; không mất tiền, không crash, chỉ một khoảng trống nhỏ trên biểu đồ.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`TradingPresenter.__init__` gọi `self.view.equity_chart.render_historical_data(...)` (đọc snapshot
backlog từ `EquityCurveRecorder`) **trước** khi gọi `self._connect_ui_signals();
self._connect_engine_events()` — hàm sau mới thực sự subscribe `EquityFeed` để nhận sample mới
qua live event. Một sample ghi vào `EquityCurveRecorder` đúng vào khoảng giữa hai điểm đó (đọc
snapshot xong, chưa subscribe xong) không nằm trong snapshot đã đọc (ghi sau khi đọc) **và** không
được live subscription bắt (subscription chưa tồn tại lúc đó) — mất trắng cho tới lần mở lại màn
hình kế tiếp (khi backlog snapshot mới sẽ chứa nó).

## 2. Root cause

Thứ tự hai bước trong constructor: đọc seed data đặt **trước** subscribe live feed, tạo ra một
cửa sổ race giữa hai nguồn dữ liệu (snapshot một-lần vs. stream liên tục) mà không có gì đảm bảo
tính liên tục giữa chúng.

## 3. Fix

Đổi thứ tự: gọi `self._connect_ui_signals(); self._connect_engine_events()` (subscribe
`EquityFeed`) **trước**, rồi mới đọc `render_historical_data(...)`. Hướng này an toàn hơn hướng
ngược lại vì lý do bất đối xứng: nếu đổi hướng gây "miss" một sample (như bug hiện tại), không có
gì tự sửa; nếu đổi hướng ngược sinh ra "duplicate" (một sample vừa lọt vào snapshot vừa được live
event bắn lại), `ChartCard.append_closed_candle()` đã có sẵn guard chống trùng theo timestamp cuối
cùng — tự triệt tiêu duplicate đó mà không cần sửa gì thêm. Chọn hướng seed-sau-subscribe vì rủi ro
còn lại (duplicate) đã có cơ chế tự chữa sẵn, còn rủi ro cũ (miss) thì không.

## 4. Regression test

`tests/unit/presentation/ui/screens/trading/test_trading_presenter_equity.py::
test_a_sample_recorded_right_at_subscribe_time_is_not_missed` — mock `IEventBus.on()` tự ghi thêm
một sample mới vào `EquityCurveRecorder` làm side effect ngay tại thời điểm `EquityFeed` subscribe
(mô phỏng chính xác cửa sổ race: một `ACCOUNT_UPDATE` tới trên luồng websocket đúng lúc đó), xác
nhận `render_historical_data(...)` được gọi với **cả hai** sample (sample cũ + sample "muộn"), không
thiếu sample nào.

Xác nhận đỏ trước fix (snapshot đọc trước khi subscribe tồn tại, sample "muộn" không nằm trong
lệnh gọi `render_historical_data`), xanh sau fix.
