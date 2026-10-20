"""`EPIC-040D` — what the Backtest workbench shows, as one value the presenter builds and the view
only applies.

The view holds no logic (`pitfalls/ui.md` §4): which command is on, which offer is visible and what
the status line says are decided here, from one state, so no text outlives the state that wrote it
(the Grid page's status line did, `EPIC-040A`).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_run_fsm_matrix import (
    RunActivity,
)


@dataclass(frozen=True, slots=True)
class WorkbenchState:
    """Everything the page reads off the presenter."""

    activity: RunActivity = RunActivity.IDLE
    #: Why Run is off; `""` when it is on.
    reason: str = ""
    status: str = ""
    offer_sync: bool = False
    offer_without_funding: bool = False
    #: Whether the selected bot's kind has a sandbox to edit and reset.
    has_sandbox: bool = False
    changed_fields: tuple[str, ...] = ()
    source_text: str = ""
    #: The question about discarding edits, `""` while none is open.
    question: str = ""
    verdict_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Controls:
    """Which command is on and which offer is visible, decided from a `WorkbenchState`."""

    run_enabled: bool
    cancel_enabled: bool
    cancel_text: str
    sync_visible: bool
    no_funding_visible: bool
    reset_enabled: bool
    editor_enabled: bool
    answer_visible: bool


def controls_of(state: WorkbenchState) -> Controls:
    """@brief While a run or a sync is in flight only Cancel is live ("Stop" when the work stores data:
    what a sync stored stays); otherwise Run is on exactly when nothing says why not."""
    busy = state.activity is not RunActivity.IDLE
    return Controls(
        run_enabled=not busy and not state.reason,
        cancel_enabled=busy,
        cancel_text="Stop" if state.activity is RunActivity.SYNCING else "Cancel",
        sync_visible=state.offer_sync and not busy,
        no_funding_visible=state.offer_without_funding and not busy,
        reset_enabled=state.has_sandbox and not busy and bool(state.changed_fields),
        editor_enabled=state.has_sandbox and not busy and not state.question,
        answer_visible=bool(state.question),
    )
