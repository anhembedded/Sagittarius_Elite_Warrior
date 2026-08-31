# EPIC-019B — `HealthCheckCoordinator` dùng chung Dashboard + Backtest

**Thuộc Epic:** [`EPIC-019`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** ADR D2.

---

## Hiện trạng

`HealthFeed` construction + wiring + 2 method trùng lặp gần như byte-for-byte:

- `src/presentation/ui/screens/dashboard/dashboard_presenter.py:777-796`
  (comment tại đây tự thừa nhận: *"Trước đây màn này tự `event_bus.on(...)`
  rồi tự ghép chuỗi, và Backtest cũng vậy"*)
- `src/presentation/ui/screens/backtest/backtest_presenter.py:572-583`

Cả 2: `self._health_feed = HealthFeed(self.event_bus, parent=self)` →
`.healthUpdated.connect(self._on_health_report)` →
`_trigger_initial_health_check()` gọi `self._health_feed.request_refresh()`
→ `_on_health_report(report)` emit `report.to_log_line()` ra log của màn
đó. Khác biệt duy nhất: Dashboard gọi `self.ui_log_signal.emit(...)`,
Backtest gọi `self._emit_ui_log(..., "info", is_dev=False)`.

## Việc cần làm

1. Tạo `HealthCheckCoordinator` (plain Python class, cùng quy ước
   Coordinator hiện có). Constructor nhận: `event_bus`, `emit_log:
   Callable[[str], None]`, `parent: QObject | None` (cho `HealthFeed` cần
   parent Qt — coordinator không phải `QObject` nhưng vẫn phải truyền
   parent xuống `HealthFeed` nó tạo).
2. Coordinator dựng `HealthFeed`, connect `healthUpdated` vào
   `_on_report()` nội bộ — `_on_report()` gọi `emit_log(report.to_log_line())`.
   `request_initial_check()` — logic của `_trigger_initial_health_check`.
3. Ở `DashboardPresenter`/`BackTestPresenter`: xoá 2 method +
   `self._health_feed` cũ, khởi tạo `HealthCheckCoordinator` trong
   `__init__`, truyền `emit_log=self.ui_log_signal.emit` (Dashboard) /
   `emit_log=lambda msg: self._emit_ui_log(msg, "info", is_dev=False)`
   (Backtest) — giữ nguyên khác biệt log hiện có, không thay đổi hành vi
   quan sát được.
4. Gọi `request_initial_check()` ở đúng chỗ 2 Presenter hiện đang gọi
   `_trigger_initial_health_check()`.

## Tiêu chí xong

- `dashboard_presenter.py`/`backtest_presenter.py` không còn tự dựng
  `HealthFeed` hay tự định nghĩa `_on_health_report` — cả 2 dùng chung
  `HealthCheckCoordinator`.
- Log hiển thị ra UI của cả 2 màn giữ nguyên định dạng như trước (test
  hiện có, nếu assert nội dung log, không đổi).
- Test FSM/health hiện có xanh không đổi assertion.

## Kết quả

- `src/presentation/ui/common/health_check_coordinator.py` (mới) —
  `HealthCheckCoordinator`, cùng hình dạng `SymbolOptionsCoordinator`
  (`EPIC-019A`): plain class, `emit_log` là callback tiêm vào constructor.
- `DashboardPresenter`: xoá đoạn dựng `HealthFeed` + `_on_health_report`
  cũ trong `_connect_engine_events`, thay bằng khởi tạo
  `HealthCheckCoordinator`; `_trigger_initial_health_check()` giữ lại như
  wrapper 1 dòng gọi `coordinator.request_initial_check()` (không đổi call
  site đang gọi nó).
- `BackTestPresenter`/`signal_wiring.connect_engine_events`: cùng thay
  đổi — wiring `HealthFeed` cũ trong hàm free-function `connect_engine_events`
  đổi thành khởi tạo `HealthCheckCoordinator` với `emit_log=lambda msg:
  presenter._emit_ui_log(msg, "info", is_dev=False)`, giữ đúng khác biệt
  log so với Dashboard.
- `HealthFeed`/`HealthStatusReport` import bị xoá khỏi 2 Presenter (không
  còn dùng trực tiếp — sống trong Coordinator).
- Test cập nhật: `tests/unit/presentation/ui/screens/test_system_health_logging.py`
  — 3 chỗ đọc `presenter._health_feed` đổi thành
  `presenter._health_check_coordinator._health_feed`.
- `290 test xanh` (health logging + backtest/dashboard presenter + common
  coordinators), 0 fail.
