# EPIC-003B — `DataManagementPresenter` → Coordinator Pattern (pilot)

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-003A`](../completed/EPIC-003A_shared_action_ownership_tracker.md).

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
    ├── scan_coordinator.py            # Quét DB shard, thống kê dung lượng
    ├── sync_coordinator.py            # Sync đơn, Bulk Sync, lắng nghe progress
    ├── gap_coordinator.py             # Quét gap, repair gap (BOT-112C)
    └── kline_inspector_coordinator.py # Load nến thô, audit toàn vẹn (BOT-112B)
```

Mỗi Coordinator nhận `view_model`, `thread_manager`, `dispatcher`, **và
tracker action-ownership của Presenter cha** qua constructor — không tự
resolve container, không tự tạo tracker riêng (đúng ràng buộc `code-rule.md`
§3).

## 3. Kiểm Thử / Nghiệm Thu

- Mọi test hiện có của `test_data_management_presenter.py` (bao gồm các
  test mới từ `BUG-018` phiên này — `test_startup_auto_discovery_*`,
  `test_unlock_ui_*`) phải pass **không đổi assertion** sau khi refactor —
  đây là bài kiểm tra thật cho "hành vi giữ nguyên, chỉ đổi cấu trúc file".
- Mỗi Coordinator có file test riêng, test được độc lập với `Mock`
  `thread_manager`/`dispatcher`/tracker — không cần dựng cả Presenter.
- `data_management_presenter.py` sau refactor còn lại đúng phần "nhạc
  trưởng": `__init__`, FSM, `_connect_ui_signals`/`_connect_engine_events`,
  action-ownership qua tracker chung — không còn logic nghiệp vụ Sync/Scan/
  Gap/KLine trực tiếp trong file này.
