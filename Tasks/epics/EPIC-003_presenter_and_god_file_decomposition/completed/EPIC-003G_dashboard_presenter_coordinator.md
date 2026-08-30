# EPIC-003G — `DashboardPresenter` → Coordinator Pattern

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-30 — quy mô nhỏ hơn dự kiến, xem "Kết quả" bên dưới
**Phụ thuộc:** [`EPIC-003A`](EPIC-003A_shared_action_ownership_tracker.md) ✅ (tracker dùng chung phải tồn tại trước — đúng ràng buộc §1 của epic).
**Nguồn:** Phát hiện khi verify report "Hard Design" bên ngoài, ratify ở
[`EPIC-017`'s ADR](../../EPIC-017_presentation_hard_design_round2/DECISION_2026-08-30_hard_design_round2.md) D5.

---

## Vì sao mở task này

Đo 2026-08-30: `dashboard_presenter.py` **1144 dòng, 43 method** (bao gồm
private) — vượt xa ngưỡng `architecture-rule.md` §5 (>400 dòng/>15 method
công khai). Khác với `backtest_presenter.py` (`EPIC-003E` ✅) và
`data_management_presenter.py` (`EPIC-003B` ✅), `dashboard_presenter.py`
**chưa từng qua Coordinator Pattern** — thư mục `screens/dashboard/` không
có `coordinators/`, chỉ có 3 file phẳng: `autostart_controller.py`,
`history_pagination_controller.py`, `stream_lifecycle_controller.py`.

## Việc đầu tiên khi mở khoá — xác nhận trước khi thiết kế

3 controller hiện có **có thể** đã đúng hình dạng Coordinator (state-holding,
tự submit việc nền) hoặc chỉ là helper thường tình cờ trùng tên. Việc đầu
tiên: đọc cả 3 file, xác nhận chúng có dùng `ActionOwnershipTracker` dùng
chung từ `EPIC-003A` chưa. Nếu **có** → việc còn lại chỉ là dời thêm logic
từ presenter ra các coordinator đã đúng dạng, không phải dựng từ đầu. Nếu
**không** → cần quyết định: nâng cấp 3 controller này lên đúng Coordinator
Pattern, hay giữ chúng và thêm coordinator mới song song (ghi rõ lý do chọn
hướng nào).

## Ràng buộc (kế thừa từ `EPIC-003` §2b)

Coordinator **không được** tự giữ FSM hay tự cài action-ownership riêng —
cơ chế đó có đúng 1 chủ sở hữu (Presenter, hoặc tracker dùng chung từ
`EPIC-003A`). Method nào test đang gọi thẳng/gán thẳng thuộc tính thì giữ
nguyên chữ ký trên presenter, thân hàm mới delegate (bài học lặp 3 lần ở
`EPIC-003E`, xem file đó).

## Tiêu chí xong

- Trích ít nhất 1 coordinator thật (state-holding, không phải helper thuần)
  ra khỏi `dashboard_presenter.py`.
- Toàn bộ test hiện có (`test_dashboard_presenter.py`,
  `test_dashboard_presenter_state.py`, …) xanh không đổi assertion.
- Ghi số dòng trước/sau vào file này khi đóng (theo đúng format `EPIC-003B`/`EPIC-003E`).

## Kết quả (2026-08-30)

**Xác nhận trước khi thiết kế (đúng như mục "Việc đầu tiên" ở trên):** 3
controller hiện có (`autostart_controller.py` 91 dòng,
`history_pagination_controller.py` 125 dòng, `stream_lifecycle_controller.py`
478 dòng) **không** dùng `ActionOwnershipTracker` — chúng thuộc một pattern
callback-injection có từ trước `EPIC-003` (thời BOT-033/034/035), không phải
Coordinator Pattern đúng nghĩa `EPIC-003A` định nghĩa, nhưng **là extraction
thật**, không phải helper thuần tình cờ trùng tên. Điều này khiến quy mô
việc còn lại nhỏ hơn nhiều so với giả định ban đầu của task (0 coordinator):
phần còn nằm trực tiếp trên presenter chỉ là chart-card lookup +
indicator-script dispatch.

**Trích `coordinators/indicator_coordinator.py`** (105 dòng) — tra chart
card theo symbol đang active, tính `fetch_limit` (BOT-034), dispatch 4 loại
dữ liệu script (line/region/info/marker) lên đúng card. Theo đúng khuôn của
`screens/backtest/coordinators/indicator_coordinator.py`: chart card tra qua
getter, không giữ tham chiếu (dict `active_charts` bị thay nguyên khối mỗi
lần rebuild).

**Bẫy lặp lại từ `EPIC-003E`, gặp lại ở đây:** `test_dashboard_presenter.py`
monkeypatch `presenter._enabled_script_keys = lambda: [...]` trên instance
ở hơn 10 chỗ. Nếu coordinator bind bound-method lúc khởi tạo, monkeypatch
sau đó vô hiệu. Sửa bằng lambda gọi `self._enabled_script_keys()` muộn (qua
`self`, không capture method) — đúng idiom đã dùng sẵn cho
`StreamLifecycleController`'s `ensure_chart_cards=lambda symbols: self._ensure_chart_cards(symbols)`.
`active_charts` **giữ nguyên** là dict thuộc presenter (không dời vào
coordinator) vì nhiều test gán lại toàn bộ `presenter.active_charts = {...}`
sau khi presenter đã dựng — coordinator giữ tham chiếu sẽ bị stale ngay.

**`_ensure_chart_cards` không trích** — quyết định có chủ đích: hàm này gắn
chặt với việc `connect()` signal trên từng card mới (`toolbar.sig_timeframe_changed`,
`card.sig_near_left_edge`), rủi ro cao hơn lợi ích so với 2 hàm dispatch kia.

| | Trước | Sau |
| :--- | ---: | ---: |
| `dashboard_presenter.py` | 1.158 dòng | **1.134** |
| `coordinators/indicator_coordinator.py` | 0 | **105** |
| Test riêng cho coordinator | 0 | **13 test** (`test_dashboard_indicator_coordinator.py`) |

Giảm ròng khiêm tốn (24 dòng) — đúng như dự đoán khi phát hiện phần lớn màn
này đã được tách trước đó; giá trị thật nằm ở việc có thêm 1 coordinator
test được độc lập, không phụ thuộc `presenter` fixture nặng.

**Verify:** `ruff check`/`format --diff` sạch. 787 test xanh (toàn bộ
`screens/` unit suite + sanity composition-root + 2 structure guard) trên
venv 3.12 + PySide6 6.11.1 + engine thật, không đổi assertion nào.
