# EPIC-003B — `DataManagementPresenter` → Coordinator Pattern (pilot)

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** ✅ Hoàn thành (2026-08-21)
**Phụ thuộc:** [`EPIC-003A`](EPIC-003A_shared_action_ownership_tracker.md).

---

## 1. Vì Sao Làm Pilot Ở Đây Trước, Không Phải `BacktestPresenter`

Đúng như chính `PRO-002` đề xuất (Giai đoạn 1) — file nhỏ hơn (919 dòng so
với 2722), và **chưa có** cơ chế action-ownership bespoke phức tạp như
`BacktestPresenter` (không có `_active_action`/`BacktestActionKind` riêng) —
rủi ro thấp hơn hẳn để chứng minh pattern trước khi áp dụng lên file rủi ro
cao nhất.

## 2. Cấu Trúc (theo `PRO-001`, đã hoà giải với `code-rule.md` §3 mới)

```text
src/presentation/ui/screens/data_management/
├── data_management_presenter.py   # Còn lại: __init__, FSM, bind signal, action-ownership (dùng tracker chung từ EPIC-003A)
├── data_management_view.py
├── data_management_view_model.py
├── DatabaseScreen.qml
└── coordinators/
    ├── __init__.py
    ├── action_kinds.py                # DataManagementActionKind enum
    ├── scan_coordinator.py            # Quét DB shard, auto-discovery, clear data, purge vault, VACUUM (injected IMarketDataRepository)
    ├── sync_coordinator.py            # Sync đơn, Bulk Sync, lắng nghe progress events, cancellation
    ├── gap_coordinator.py             # Quét gap, repair gap (BOT-112C), cancellation
    └── kline_inspector_coordinator.py # Load nến thô, audit toàn vẹn (BOT-112B)
```

Mỗi Coordinator nhận `view_model` (khi cần), `thread_manager`, `dispatcher`, **và
tracker action-ownership của Presenter cha** qua constructor — không tự
resolve container, không tự tạo tracker riêng (đúng ràng buộc `code-rule.md`
§3).

## 3. Kiểm Thử / Nghiệm Thu

- Toàn bộ 42 test hiện có (`test_data_management_presenter.py`, `test_gap_inspector_presenter.py`, `test_kline_inspector_presenter.py`, `test_database_progress_cancel_qml.py`) pass 100% không đổi bất kỳ assertion nào.
- 4 file unit test mới cho từng Coordinator độc lập:
  - `test_scan_coordinator.py` (5 tests)
  - `test_sync_coordinator.py` (5 tests)
  - `test_gap_coordinator.py` (3 tests)
  - `test_kline_inspector_coordinator.py` (2 tests)
  Tổng cộng 57/57 tests pass 100%.
- DI Sanity: 9/9 database DI sanity tests pass 100%.
- `data_management_presenter.py` đóng vai trò đúng nghĩa Orchestrator: FSM transitions, signal binding, UI unlock, và tracker action ownership, delegate toàn bộ business workflows sang 4 Coordinators.
