from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)


class DummyKind(str, Enum):
    FETCH = "FETCH"
    PROCESS = "PROCESS"


class DummyState(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"


@dataclass
class DummyConfig:
    name: str
    items: list[int]

    def to_summary_label(self) -> str:
        return f"Config({self.name}, {len(self.items)} items)"


def test_tracker_initial_state() -> None:
    tracker = ActionOwnershipTracker[DummyKind, DummyConfig, DummyState]()
    assert tracker.active_action is None
    assert tracker.active_outcome is None
    assert tracker.current_action_id(DummyKind.FETCH) is None
    assert tracker.is_current(1, DummyKind.FETCH) is False
    assert tracker.is_current_pending(1, DummyKind.FETCH) is False


def test_begin_action_creates_immutable_context_and_sets_pending() -> None:
    traces: list[tuple[str, dict[str, object]]] = []

    def on_trace(action: str, **fields: object) -> None:
        traces.append((action, fields))

    tracker = ActionOwnershipTracker[DummyKind, DummyConfig, DummyState](
        on_trace=on_trace
    )
    config = DummyConfig(name="test_1", items=[1, 2])

    ctx = tracker.begin_action(DummyKind.FETCH, config, DummyState.IDLE)

    assert ctx.action_id == 1
    assert ctx.kind is DummyKind.FETCH
    assert ctx.previous_state is DummyState.IDLE
    assert ctx.config.items == [1, 2]
    assert tracker.active_action == ctx
    assert tracker.active_outcome is ActionOutcome.PENDING

    # Verify deep copy of mutable config
    config.items.append(3)
    assert ctx.config.items == [1, 2]

    # Verify trace log
    assert len(traces) == 1
    assert traces[0][0] == "action_started"
    assert traces[0][1]["action_id"] == 1
    assert traces[0][1]["kind"] == "FETCH"
    assert traces[0][1]["previous_state"] == "IDLE"
    assert "Config(test_1, 2 items)" in str(traces[0][1]["config"])


def test_begin_action_supersedes_previous_pending_action() -> None:
    traces: list[tuple[str, dict[str, object]]] = []

    def on_trace(action: str, **fields: object) -> None:
        traces.append((action, fields))

    tracker = ActionOwnershipTracker[DummyKind, DummyConfig, DummyState](
        on_trace=on_trace
    )
    ctx1 = tracker.begin_action(
        DummyKind.FETCH, DummyConfig("c1", [1]), DummyState.IDLE
    )
    assert tracker.active_action == ctx1
    assert tracker.active_outcome is ActionOutcome.PENDING

    ctx2 = tracker.begin_action(
        DummyKind.PROCESS, DummyConfig("c2", [2]), DummyState.BUSY
    )
    assert ctx2.action_id == 2
    assert tracker.active_action == ctx2
    assert tracker.active_outcome is ActionOutcome.PENDING

    # ctx1 is no longer current
    assert tracker.is_current(ctx1.action_id, ctx1.kind) is False
    assert tracker.is_current_pending(ctx1.action_id, ctx1.kind) is False

    # ctx2 is current and pending
    assert tracker.is_current(ctx2.action_id, DummyKind.PROCESS) is True
    assert tracker.is_current_pending(ctx2.action_id, DummyKind.PROCESS) is True
    assert tracker.current_action_id(DummyKind.PROCESS) == 2
    assert tracker.current_action_id(DummyKind.FETCH) is None

    # Verify superseding trace events
    action_names = [t[0] for t in traces]
    assert "action_superseded" in action_names
    assert "action_finished" in action_names
    assert "action_started" in action_names


def test_finish_action_updates_outcome_only_for_matching_id() -> None:
    tracker = ActionOwnershipTracker[DummyKind, DummyConfig, DummyState]()
    ctx = tracker.begin_action(DummyKind.FETCH, DummyConfig("c1", []), DummyState.IDLE)

    # Wrong action_id has no effect
    result_wrong = tracker.finish_action(999, ActionOutcome.SUCCEEDED)
    assert result_wrong is False
    assert tracker.active_outcome is ActionOutcome.PENDING
    assert tracker.is_current_pending(ctx.action_id, DummyKind.FETCH) is True

    # Matching action_id finishes action
    result_ok = tracker.finish_action(ctx.action_id, ActionOutcome.SUCCEEDED)
    assert result_ok is True
    assert tracker.active_outcome is ActionOutcome.SUCCEEDED
    assert tracker.is_current(ctx.action_id, DummyKind.FETCH) is True
    assert tracker.is_current_pending(ctx.action_id, DummyKind.FETCH) is False


def test_invalidate_active_marks_pending_as_invalidated() -> None:
    tracker = ActionOwnershipTracker[DummyKind, DummyConfig, DummyState]()
    ctx = tracker.begin_action(DummyKind.FETCH, DummyConfig("c1", []), DummyState.IDLE)

    tracker.invalidate_active()
    assert tracker.active_outcome is ActionOutcome.INVALIDATED
    assert tracker.is_current(ctx.action_id, DummyKind.FETCH) is True
    assert tracker.is_current_pending(ctx.action_id, DummyKind.FETCH) is False

    # Calling invalidate_active again on already invalidated action does nothing
    tracker.invalidate_active()
    assert tracker.active_outcome is ActionOutcome.INVALIDATED


def test_log_stale_callback_emits_trace() -> None:
    traces: list[tuple[str, dict[str, object]]] = []

    def on_trace(action: str, **fields: object) -> None:
        traces.append((action, fields))

    tracker = ActionOwnershipTracker[DummyKind, DummyConfig, DummyState](
        on_trace=on_trace
    )
    ctx = tracker.begin_action(DummyKind.FETCH, DummyConfig("c1", []), DummyState.IDLE)
    tracker.finish_action(ctx.action_id, ActionOutcome.SUCCEEDED)

    tracker.log_stale_callback("on_fetch_done", 999, DummyKind.FETCH)

    stale_traces = [t for t in traces if t[0] == "action_callback_ignored"]
    assert len(stale_traces) == 1
    assert stale_traces[0][1]["callback"] == "on_fetch_done"
    assert stale_traces[0][1]["action_id"] == 999
    assert stale_traces[0][1]["kind"] == "FETCH"
    assert stale_traces[0][1]["active_action_id"] == 1
    assert stale_traces[0][1]["active_outcome"] == "SUCCEEDED"
