# EPIC-003A — Trích xuất cơ chế Action-Ownership dùng chung

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** ✅ **Hoàn thành (2026-08-21)** — implement bởi AI khác (theo yêu cầu user), review lại bằng cách đọc code thật trước khi merge, sửa thêm 3 lỗi lint sau merge.
**Phụ thuộc:** Không có — bắt buộc làm **trước** `EPIC-003B`/`EPIC-003E`.

---

## 0. Kết quả thật

**Quyết định cho câu hỏi thiết kế ở mục 2:** chọn **app-local** —
`src/presentation/ui/common/action_ownership_tracker.py`. Thư mục
`ui/common/` đã tồn tại sẵn từ trước với đúng vai trò này
(`base_event_logger.py` — 1 primitive dùng chung nhiều Presenter cùng lý
do), củng cố thêm cho lựa chọn này thay vì đặt lên `sagittarius_engine`
(tránh sửa cross-repo không cần thiết, đúng nguyên tắc "không sửa engine
trừ khi thật sự thiếu cơ chế nền" của `ONBOARDING.md` §2).

**Đã build:** `ActionOutcome` (Enum, 6 giá trị khớp y hệt
`BacktestActionOutcome` cũ), `ActionContext[TKind, TConfig, TState]`
(dataclass frozen, generic PEP 695), `ActionOwnershipTracker[TKind, TConfig,
TState]` (`begin_action`, `is_current`, `is_current_pending`,
`current_action_id`, `finish_action`, `invalidate_active`,
`log_stale_callback`), `ActionTraceCallback` (`Protocol` khớp đúng chữ ký
`**fields: object` thật của `_log_dev_trace`, không phải `dict` như bản
draft ban đầu — xem "Review trước khi merge" bên dưới).

**Quyết định thiết kế quan trọng nhất, không có trong bản draft ban đầu:**
`is_cancelling()` **không** đưa vào tracker. Đọc code thật
(`_is_cancelling_action`) xác nhận nó cần **4 điều kiện**, trong đó 2 điều
kiện (`_cancelling_action_id` — biến riêng, và `self.fsm.current_state is
CANCELLING` — đọc thẳng FSM của Presenter) tracker generic **không thể**
biết được. Giữ nguyên 2 điều kiện đó ở `BacktestPresenter`, chỉ 2 điều kiện
còn lại (`action_id`, `outcome`) đi qua tracker. Đây chính xác là ranh giới
`code-rule.md` §3 đã đặt ra: tracker sở hữu action-id/generation, Presenter
sở hữu FSM — không được lẫn vào nhau.

**Review trước khi merge (đọc code thật, không chỉ đọc plan):** bản kế
hoạch (do AI khác viết) ban đầu có 3 vấn đề nếu implement đúng y hệt sẽ hỏng
hành vi hoặc lỗi type — bản implement thật đã tự sửa đúng cả 3 trước khi
tôi review tới, xác nhận bằng cách đọc code sau merge:
1. `is_cancelling()` không bị nhét vào tracker (xem trên) — đúng.
2. `on_trace` dùng `Protocol` với `**fields: object` khớp đúng
   `_log_dev_trace` thật, không phải `Callable[[str, dict[str, Any]], None]`
   như plan gốc — đúng.
3. `kind` là tham số bắt buộc, không phải `TKind | None = None` — khớp thực
   tế mọi call site thật (~17 chỗ) đều luôn truyền `kind` — đúng.

**2 lỗi lint thật tìm thấy sau merge, đã sửa:** `ActionContext`/
`ActionOwnershipTracker` dùng `class Foo(Generic[T]):` kiểu cũ thay vì PEP
695 `class Foo[T]:` — không khớp tiền lệ đã có trong codebase
(`ICommandHandler[TCommand_contra, TResponse_co](Protocol)` ở `i_cqrs.py`).
Đổi sang PEP 695, xoá `TypeVar`/`Generic` import không còn cần. Cộng 1 lỗi
`I001` (import sort) trong `backtest_presenter.py`.

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

**Kết quả thật:** `tests/unit/presentation/ui/common/test_action_ownership_tracker.py`
(mới, 8 test — supersede, fencing, finish_action, invalidate, stale
callback) + `tests/unit/presentation/ui/screens/test_backtest_presenter.py`
(có sẵn từ trước, **xác nhận qua `git diff` không hề bị sửa 1 dòng nào**,
đúng yêu cầu "không đổi assertion") — **172 test pass**. `mypy` gate
(`EPIC-002B`) sạch trên toàn bộ `src`+`scripts` sau refactor. `ruff`
check/format sạch sau khi sửa 2 lỗi `UP046` + 1 lỗi `I001` nêu ở mục 0.
