# EPIC-003A — Trích xuất cơ chế Action-Ownership dùng chung

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** Không có — bắt buộc làm **trước** `EPIC-003B`/`EPIC-003E`.

---

## 1. Vì Sao Task Này Bắt Buộc Đứng Đầu

`code-rule.md` §3 (Coordinator Pattern) giờ cấm Coordinator tự cài action-id/
generation fencing riêng — cơ chế đó phải có đúng 1 chủ sở hữu. Đọc thật
`backtest_presenter.py` hiện tại (`_next_action_id`, `_active_action`,
`_is_current_action`, `_is_current_pending_action`, `_current_action_id`,
`_finish_action`, `_invalidate_active_action`, `_ignore_stale_action_callback`
— khoảng 150 dòng, key theo `BacktestActionKind`/`BacktestActionOutcome`
riêng của presenter này) xác nhận: cơ chế này **đã tồn tại thật**, nhưng
đang **bespoke, không dùng chung được**. Nếu bắt đầu tách Coordinator trước
khi có bản dùng chung, mỗi Coordinator mới sẽ phải tự nghĩ lại đúng cơ chế
này — rủi ro lệch nhau âm thầm, đúng lớp lỗi `BUG-018`.

## 2. Câu Hỏi Thiết Kế Chưa Tự Quyết — Cần Bàn Trước Khi Code

**Primitive này nên sống ở `sagittarius_engine` (framework, dùng chung mọi
Presenter của mọi app) hay ở `Sagittarius_Elite_Warrior` (app-local, chỉ
dùng nội bộ)?**

- Nghiêng về **engine**: đây là pattern MVP hoàn toàn tổng quát (1 action
  đang chờ, action mới đến thì action cũ bị invalidate, callback trễ bị bỏ
  qua) — không có gì đặc thù cho backtest hay app này. `BasePresenter` (nơi
  tự nhiên nhất để đặt primitive này) đã sống ở engine.
- Nghiêng về **app-local**: sửa `sagittarius_engine` là sửa cross-repo, kéo
  theo phải test/release đồng bộ cả 2 repo — chi phí lớn hơn hẳn so với 1
  module mới trong `Sagittarius_Elite_Warrior/src/presentation/`.

**Không tự quyết ở đây — quyết định trước khi viết code, không phải sau.**

## 3. Yêu Cầu Kỹ Thuật (áp dụng dù chọn nhánh nào ở mục 2)

- Trích xuất thành 1 class chung (`ActionOwnershipTracker` hoặc tên tương
  đương): `begin_action(kind) -> ActionContext`, `is_current(action_id, kind)`,
  `finish_action(action_id, outcome)`, `invalidate_active()`. Generic theo
  `kind` (không gắn cứng `BacktestActionKind`) — mỗi Presenter tự định nghĩa
  Enum `kind` của mình, tracker không cần biết ý nghĩa domain của từng kind.
- `BacktestPresenter` refactor để dùng tracker này thay vì cơ chế tự viết —
  **hành vi phải giữ nguyên y hệt** (mọi test action-ownership/cancellation
  hiện có của `backtest_presenter.py` phải pass không sửa assertion).
- Coordinator (từ `EPIC-003B` trở đi) nhận **tham chiếu tới tracker của
  Presenter cha** qua constructor injection, không tự tạo tracker riêng.

## 4. Kiểm Thử

- Test đơn vị cho tracker: action mới supersede action cũ đúng cách
  (`INVALIDATED`), callback trễ (action_id không khớp `is_current`) bị bỏ
  qua, `finish_action` với `action_id` sai không có tác dụng.
- Toàn bộ test hiện có của `backtest_presenter.py` liên quan cancellation/
  stale-callback (từ `BOT-095C`, xem `code-rule.md` §2.8) phải pass không
  đổi assertion sau khi refactor sang dùng tracker chung.
