# EPIC-003G — `DashboardPresenter` → Coordinator Pattern

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
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
