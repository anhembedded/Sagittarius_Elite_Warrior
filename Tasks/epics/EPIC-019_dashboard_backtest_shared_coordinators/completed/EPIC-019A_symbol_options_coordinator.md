# EPIC-019A — `SymbolOptionsCoordinator` dùng chung Dashboard + Backtest

**Thuộc Epic:** [`EPIC-019`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** ADR D1.

---

## Hiện trạng

4 method + 1 field trùng lặp gần như byte-for-byte giữa 2 Presenter:

- `src/presentation/ui/screens/dashboard/dashboard_presenter.py:599-630`
  (`_on_symbol_picker_open_requested`, `_fetch_symbol_options`,
  `_on_symbol_options_ready`, `_on_symbol_options_failed`,
  `self._symbol_options_cache`)
- `src/presentation/ui/screens/backtest/backtest_presenter.py:1378-1409`
  (cùng 4 method, cùng field, khác duy nhất dòng emit log cuối cùng của
  `_on_symbol_options_failed`)

Cả hai đều: check cache → nếu miss thì `thread_manager.submit(fetch)` →
worker thread dispatch `ListAvailableSymbolsQuery` → emit ready/failed
signal → main-thread slot ghi cache + gọi `view_model.set_symbol_options()`.

## Việc cần làm

1. Tạo `SymbolOptionsCoordinator` (plain Python class, không `QObject` —
   đúng quy ước Coordinator hiện có, ví dụ
   `src/presentation/ui/screens/dashboard/coordinators/indicator_coordinator.py`).
   Constructor nhận: `dispatcher`, `thread_manager`, `emit_ready:
   Callable[[list[str]], None]`, `emit_failed: Callable[[str], None]`.
2. Coordinator giữ `_symbol_options_cache` (chuyển từ Presenter).
   `request_open()` — logic của `_on_symbol_picker_open_requested`.
   `_fetch()` — logic của `_fetch_symbol_options`, dispatch
   `ListAvailableSymbolsQuery`, gọi `emit_ready`/`emit_failed` thay vì tự
   emit signal Qt.
3. Ở `DashboardPresenter`/`BackTestPresenter`: xoá 4 method + field cũ,
   khởi tạo `SymbolOptionsCoordinator` trong `__init__` (sau khi
   `self._thread_manager` đã resolve), nối `emit_ready=self._symbolOptionsReadySignal.emit`,
   `emit_failed=self._symbolOptionsFailedSignal.emit` (Presenter vẫn giữ
   signal Qt của mình — chỉ chuyển thân method logic sang Coordinator).
   Slot `_on_symbol_options_ready`/`_on_symbol_options_failed` (đã kết nối
   với signal) giữ nguyên ở Presenter — chỉ còn 2 dòng: cập nhật ViewModel
   + (với failed) emit log qua callback riêng của từng Presenter (Dashboard
   vs Backtest log khác nhau, giữ nguyên khác biệt này ở Presenter, không
   đẩy vào Coordinator).
4. `_on_symbol_picker_open_requested`/`_on_symbol_picker_refresh_requested`
   ở cả 2 Presenter đổi thành gọi thẳng `self._symbol_options_coordinator.request_open()`.

## Tiêu chí xong

- `dashboard_presenter.py`/`backtest_presenter.py` không còn định nghĩa
  `_fetch_symbol_options` riêng — cả 2 gọi vào cùng
  `SymbolOptionsCoordinator`.
- Test hiện có cho luồng fetch/cache/ready/failed symbol options ở cả 2
  màn (nếu có) xanh không đổi assertion hành vi quan sát được (chỉ đổi nơi
  logic sống).
- `sagittarius_engine`/`ListAvailableSymbolsQuery` không đổi hợp đồng.

## Kết quả

- `src/presentation/ui/common/symbol_options_coordinator.py` (mới) —
  `SymbolOptionsCoordinator`, đúng hình dạng `IndicatorCoordinator`
  (`EPIC-003G`): plain class, không `QObject`, `emit_ready`/`emit_failed`
  là callable tiêm vào constructor thay vì Coordinator tự giữ Qt signal.
- `DashboardPresenter`/`BackTestPresenter`: xoá `_fetch_symbol_options` +
  field cache cũ, khởi tạo `SymbolOptionsCoordinator` ngay sau khi
  `self._thread_manager` resolve (Backtest phải **dời** field cache cũ từ
  chỗ construct sớm — trước `self._thread_manager` — sang sau đó, vì
  Coordinator cần `thread_manager` lúc dựng). `_on_symbol_picker_open_requested`
  chỉ còn gọi `coordinator.request_open()`; `_on_symbol_options_ready` gọi
  `coordinator.on_options_ready(symbols)` rồi cập nhật ViewModel — khác biệt
  log lúc fail (Dashboard vs Backtest) giữ nguyên ở Presenter, không đẩy
  vào Coordinator, đúng quyết định trong task.
- `ListAvailableSymbolsQuery` import bị xoá khỏi cả 2 Presenter (không còn
  dùng trực tiếp — sống trong Coordinator).
- Test mới: `tests/unit/presentation/ui/common/test_symbol_options_coordinator.py`
  (4 test — fetch+ready, cache no-op, fetch failure, `on_options_ready`
  độc lập). `tests/unit/presentation/ui/screens/test_backtest_presenter.py`
  cập nhật 4 test đọc thẳng field/method cũ sang đọc qua
  `presenter._symbol_options_coordinator`.
- `240 test xanh` (`test_symbol_options_coordinator.py` +
  `test_backtest_presenter.py` + `test_dashboard_presenter.py`), 0 fail.
  `mypy` sạch trên `symbol_options_coordinator.py`; so `mypy` trước/sau
  trên 2 Presenter — **cùng 35 lỗi**, chỉ số dòng dịch (do code ngắn lại),
  không lỗi mới.
