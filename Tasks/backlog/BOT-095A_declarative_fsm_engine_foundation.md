# Nhiệm vụ: BOT-095A — Hạ tầng Declarative State Machine & Event Dispatching (`sagittarius_engine.extensions.fsm`)

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> **Trọng tâm**: Xây dựng hạ tầng máy trạng thái hướng sự kiện khai báo (`DeclarativeStateMachine[StateT, EventT]`) trong tầng Engine (`sagittarius_engine`), cho phép định nghĩa vòng đời UI bằng ma trận sự kiện tập trung `(State, Event) -> NextState`, hỗ trợ `dispatch(event)`, tự động nạp ma trận từ dict/JSON/dataclass, và tái sử dụng nhất quán cho toàn bộ các màn hình trong ứng dụng (Backtest, Dev Board, Data Management).

---

## 1. Vấn đề Hiện tại của `BaseStateMachine`

1. **Chỉ hỗ trợ chuyển trạng thái trực tiếp (`transition_to(State)`):**
   - Hiện tại, `BaseStateMachine` trong `sagittarius_engine/extensions/fsm/state_machine.py` chỉ cho phép khai báo `add_transition(from_state, to_state)`.
   - Khi có sự kiện xảy ra ở Presenter hoặc Background Worker, code phải tự tính toán xem nên gọi `transition_to(TargetState)` nào $\rightarrow$ Logic rải rác trong các hàm slots, dễ xảy ra chuyển trạng thái trái phép (illegal transitions) hoặc double-fault.
2. **Không có khái niệm Sự kiện (Events / Triggers):**
   - FSM hiện tại không phân biệt được: *Cùng ở trạng thái `RUNNING`, nếu nhận event `CANCEL_REQUESTED` thì sang đâu, còn nhận `BACKTEST_SUCCEEDED` thì sang đâu*.
3. **Chưa hỗ trợ nạp khai báo hàng loạt (Declarative Bulk Loading):**
   - Phải gọi `add_transition` từng dòng một trong `__init__`, không có khả năng đọc từ Ma trận Khai báo (Transition Table) tập trung.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Lớp `DeclarativeStateMachine[StateT, EventT]` trong `sagittarius_engine`
Được xây dựng trong `sagittarius_engine/extensions/fsm/declarative_state_machine.py` (hoặc mở rộng trực tiếp `BaseStateMachine`):

```python
import logging
import threading
from enum import Enum
from typing import Callable, Dict, Generic, List, NamedTuple, Optional, Set, Tuple, TypeVar

StateT = TypeVar("StateT", bound=Enum)
EventT = TypeVar("EventT", bound=Enum)

logger = logging.getLogger("Engine.FSM")


class TransitionRule(NamedTuple, Generic[StateT, EventT]):
    from_state: StateT
    event: EventT
    to_state: StateT
    guard: Optional[Callable[[], bool]] = None
    action: Optional[Callable[[], None]] = None


class DeclarativeStateMachine(Generic[StateT, EventT]):
    """
    @brief Thread-safe Declarative Finite State Machine driven by Events & Transition Matrix.
    @details
    Enforces clean state transitions via dispatching formal events:
        fsm.dispatch(event) -> looks up (current_state, event) in matrix -> transitions to next_state.
    """

    def __init__(self, initial_state: StateT):
        if not isinstance(initial_state, Enum):
            raise TypeError("initial_state must be an instance of Enum")

        self._current_state: StateT = initial_state
        self._lock = threading.RLock()
        self._is_dispatching: bool = False
        self._event_queue: List[EventT] = []

        # Ma trận chuyển đổi: (from_state, event) -> TransitionRule
        self._transition_matrix: Dict[Tuple[StateT, EventT], TransitionRule[StateT, EventT]] = {}

        # Callbacks
        self._on_enter: Dict[StateT, List[Callable[[], None]]] = {}
        self._on_exit: Dict[StateT, List[Callable[[], None]]] = {}
        self._global_callbacks: List[Callable[[StateT, StateT, EventT], None]] = []

    @property
    def current_state(self) -> StateT:
        with self._lock:
            return self._current_state

    def load_matrix(self, matrix: Dict[Tuple[StateT, EventT], StateT]) -> None:
        """
        @brief Nạp toàn bộ bảng ma trận chuyển đổi khai báo từ Dict hoặc Schema.
        """
        with self._lock:
            for (from_state, event), to_state in matrix.items():
                self.add_rule(from_state, event, to_state)

    def add_rule(
        self,
        from_state: StateT,
        event: EventT,
        to_state: StateT,
        guard: Optional[Callable[[], bool]] = None,
        action: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        @brief Đăng ký một luật chuyển đổi dựa trên Sự kiện.
        """
        with self._lock:
            rule = TransitionRule(
                from_state=from_state,
                event=event,
                to_state=to_state,
                guard=guard,
                action=action,
            )
            self._transition_matrix[(from_state, event)] = rule

    def can_dispatch(self, event: EventT) -> bool:
        """
        @brief Kiểm tra xem một sự kiện có hợp lệ tại trạng thái hiện tại hay không.
        """
        with self._lock:
            rule = self._transition_matrix.get((self._current_state, event))
            if rule is None:
                return False
            if rule.guard is not None and not rule.guard():
                return False
            return True

    def dispatch(self, event: EventT) -> bool:
        """
        @brief Phát một sự kiện để kích hoạt chuyển trạng thái theo ma trận.
        Bảo vệ chống Re-entrancy bằng Hàng đợi Sự kiện (Event Queue).
        @raises InvalidStateTransitionError nếu sự kiện không hợp lệ tại trạng thái hiện tại.
        """
        with self._lock:
            # 1. Bảo vệ chống Re-entrancy: Nếu đang xử lý dispatch lồng, xếp hàng đợi
            if self._is_dispatching:
                self._event_queue.append(event)
                logger.debug(f"FSM Re-entrancy detected: Queued event {event.name}")
                return True

            self._is_dispatching = True
            try:
                self._process_dispatch(event)

                # Xử lý tuần tự các event bị lồng trong hàng đợi
                while self._event_queue:
                    queued_event = self._event_queue.pop(0)
                    self._process_dispatch(queued_event)

                return True
            finally:
                self._is_dispatching = False

    def _process_dispatch(self, event: EventT) -> None:
        current = self._current_state
        key = (current, event)
        rule = self._transition_matrix.get(key)

        if rule is None:
            logger.error(f"FSM Error: Event {event.name} is invalid in state {current.name}.")
            raise InvalidStateTransitionError(current.name, f"via event {event.name}")

        if rule.guard is not None and not rule.guard():
            logger.warning(f"FSM Guard rejected transition from {current.name} via {event.name}.")
            return

        next_state = rule.to_state
        logger.debug(f"FSM: {current.name} --({event.name})--> {next_state.name}")

        # a. on_exit callbacks
        for cb in self._on_exit.get(current, []):
            cb()

        # b. rule-specific action callback
        if rule.action is not None:
            rule.action()

        # c. Transition
        self._current_state = next_state

        # d. Global transition callbacks
        for g_cb in self._global_callbacks:
            g_cb(current, next_state, event)

        # e. on_enter callbacks
        for cb in self._on_enter.get(next_state, []):
            cb()

```

### 2.2. Tích hợp vào `BasePresenter` (`sagittarius_engine.extensions.pyside_mvc`)
- Cho phép `BasePresenter` chấp nhận một `DeclarativeStateMachine` hoặc `FSM_MATRIX` được khai báo ở lớp con:
  ```python
  class BasePresenter:
      FSM_MATRIX = None  # Dict[Tuple[StateT, EventT], StateT]
  ```
- Nếu Presenter con khai báo `FSM_MATRIX`, `BasePresenter` tự động khởi tạo `DeclarativeStateMachine` và nạp bảng ma trận.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- 🆕 `sagittarius_engine/extensions/fsm/declarative_state_machine.py`: Triển khai lớp `DeclarativeStateMachine`.
- ✏️ `sagittarius_engine/extensions/fsm/__init__.py`: Export `DeclarativeStateMachine`, `TransitionRule`.
- ✏️ `sagittarius_engine/extensions/pyside_mvc/base_presenter.py`: Tích hợp hỗ trợ `FSM_MATRIX`.
- 🆕 `tests/unit/engine/test_declarative_state_machine.py` (hoặc trong repo Warrior): Viết bộ unit test toàn diện 100% độ phủ cho `DeclarativeStateMachine` (kiểm tra `dispatch`, `can_dispatch`, `load_matrix`, `guard`, `action`, thread-safety).

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Đầy đủ tính năng FSM hướng sự kiện**:
   - `load_matrix()` nạp được hàng chục luật chuyển đổi từ Dict chỉ với 1 dòng code.
   - `dispatch(event)` chuyển đúng trạng thái theo ma trận; `can_dispatch(event)` trả về `True`/`False` chính xác.
   - Raise `InvalidStateTransitionError` khi dispatch một event không có trong ma trận của trạng thái hiện tại.
2. **An toàn đa luồng (Thread-Safety)**:
   - Stress test nhiều luồng đồng thời gọi `dispatch()` không gây race condition hay deadlock.
3. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.
