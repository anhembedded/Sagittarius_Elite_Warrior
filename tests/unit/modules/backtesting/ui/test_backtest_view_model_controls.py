"""`controlsEnabled` on the Backtest view model: the one switch the Run setup
panel, the top panel and the Backtest commands read to lock their inputs
while a run, a cancel or a sync is under way.

Ported from `test_shared_ui_state_foundation.py`, deleted with the QML layer
in `EPIC-033M`: its `controlsEnabled` tests were plain Python and still guard
what `run_setup_panel.py`, `backtest_top_panel.py` and
`backtest_command_binding.py` rely on, the change signal included. They now
run against the app's own view model rather than a probe subclass, so they
keep holding when `BUG-152` moves it off the Engine's `BaseQmlViewModel`.

Retire when: no Backtest widget reads `controlsEnabled` any more.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestUiState,
)

_LOCKING = (
    BacktestUiState.RUNNING,
    BacktestUiState.CANCELLING,
    BacktestUiState.SYNCING,
)


def test_the_controls_start_enabled(qapp) -> None:
    assert BackTestViewModel().controlsEnabled is True


@pytest.mark.parametrize("state", _LOCKING)
def test_a_run_a_cancel_or_a_sync_locks_the_controls_and_idle_frees_them(
    qapp, state: BacktestUiState
) -> None:
    view_model = BackTestViewModel()

    view_model.set_ui_mode(state.value)
    assert view_model.controlsEnabled is False

    view_model.set_ui_mode(BacktestUiState.IDLE.value)
    assert view_model.controlsEnabled is True


@pytest.mark.parametrize(
    "state",
    [state for state in BacktestUiState if state not in _LOCKING],
)
def test_every_other_state_leaves_the_controls_enabled(
    qapp, state: BacktestUiState
) -> None:
    view_model = BackTestViewModel()

    view_model.set_ui_mode(state.value)

    assert view_model.controlsEnabled is True


def test_the_change_signal_fires_only_when_the_controls_flip(qapp) -> None:
    view_model = BackTestViewModel()
    flips: list[bool] = []
    view_model.controlsEnabledChanged.connect(
        lambda: flips.append(view_model.controlsEnabled)
    )

    view_model.set_ui_mode(BacktestUiState.RUNNING.value)  # enabled -> locked
    view_model.set_ui_mode(BacktestUiState.CANCELLING.value)  # still locked
    view_model.set_ui_mode(BacktestUiState.COMPLETED.value)  # locked -> enabled
    view_model.set_ui_mode(BacktestUiState.IDLE.value)  # still enabled

    assert flips == [False, True]
