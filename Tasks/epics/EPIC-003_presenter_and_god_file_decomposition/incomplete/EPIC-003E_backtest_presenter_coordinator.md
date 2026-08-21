# EPIC-003E — `BacktestPresenter` → Coordinator Pattern

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-003A`](../completed/EPIC-003A_shared_action_ownership_tracker.md) **và** [`EPIC-003B`](EPIC-003B_data_management_coordinator_pilot.md) — không bắt đầu file rủi ro cao nhất trước khi pattern đã chứng minh đúng ở pilot.

---

## 1. Vì Sao Đây Là Task Rủi Ro Nhất Trong Nhóm Coordinator

`backtest_presenter.py` (2722 dòng) là file lớn nhất codebase, **đã có** cơ
chế action-ownership bespoke phức tạp nhất (`_active_action`,
`BacktestActionKind`/`BacktestActionOutcome`, cancellation cooperative —
xem `EPIC-003A` §1) và đụng tới nhiều luồng nghiệp vụ đan xen thật sự khó
tách sạch: Static/Realtime execution, data-sync-before-run, chart render
(Python/Native), indicator/script overlay, trade log, strategy config.

**Không bắt đầu task này trước khi `EPIC-003A` xong** (tracker dùng chung
đã có) **và `EPIC-003B` xong** (pattern đã chứng minh đúng trên 1 presenter
nhỏ hơn, có bằng chứng test thật, không phải lý thuyết).

## 2. Cấu Trúc (theo `PRO-002` §2.1)

```text
src/presentation/ui/screens/backtest/coordinators/
├── execution_coordinator.py       # Static/Realtime run, cancellation, progress
├── data_sync_coordinator.py       # Range coverage check, auto-sync thiếu dữ liệu
├── chart_render_coordinator.py    # Đồng bộ dữ liệu sang Chart Host (Python/Native)
├── indicator_coordinator.py       # Script/Indicator overlay
├── trade_log_coordinator.py       # Format, phân trang, xuất CSV Trade Log
└── strategy_config_coordinator.py # Binding tham số chiến lược, SL/TP, Đòn bẩy
```

Mỗi Coordinator dùng tracker action-ownership chung từ `EPIC-003A`, không tự
cài lại `_active_action`/`BacktestActionKind` riêng.

## 3. Ràng Buộc Đặc Thù Cần Giữ Nguyên (rút ra từ việc đã đọc/sửa file này nhiều lần trong phiên trước)

- **Backtest chart host boundary** (`code-rule.md` §2): `chart_render_coordinator.py`
  phải giữ đúng ranh giới Protocol Python/Native đã có, không để 2 nơi cùng
  sở hữu quyết định fallback native → Python.
- **`NativeUnsupportedFeatureError` fallback** phải tiếp tục hoạt động đúng
  sau khi tách — có test riêng cho nhánh fallback này từ trước (`BOT-098F6D`),
  test đó phải pass không đổi.
- Trend-zone/script region cleanup (`BOT-113`) và trade log export (đã sửa
  cột `side` ở nhánh khác) phải được phân đúng coordinator, không rơi vào
  khoảng trống giữa 2 coordinator.

## 4. Kiểm Thử / Nghiệm Thu

- Toàn bộ test hiện có của `test_backtest_presenter.py` (file test lớn
  nhất, nhiều test cancellation/stale-callback nhất) phải pass **không đổi
  assertion** — bằng chứng bắt buộc, không thương lượng, cho task rủi ro
  cao nhất của cả epic.
- `ci-local.ps1 -Full` xanh hoàn toàn sau khi refactor, bao gồm cả `mypy`
  gate (`EPIC-002`) không phát sinh lỗi mới.
