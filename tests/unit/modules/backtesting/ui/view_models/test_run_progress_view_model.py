"""`EPIC-003F5a` — `RunProgressViewModel` on its own."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.run_progress_view_model import (
    IDLE_PERCENT,
    IDLE_TEXT,
    RunProgressViewModel,
)


def test_a_fresh_view_model_shows_both_bars_idle(qapp) -> None:
    vm = RunProgressViewModel()

    assert vm.backtestProgressPercent == IDLE_PERCENT
    assert vm.backtestProgressText == IDLE_TEXT
    assert vm.syncProgressPercent == IDLE_PERCENT
    assert vm.syncProgressText == IDLE_TEXT


def test_percent_and_caption_move_together_on_one_emit(qapp) -> None:
    """One signal per bar, not one per field: two emits for one update is
    how a bar renders this run's percent under the previous run's
    caption."""
    vm = RunProgressViewModel()
    seen: list[tuple[float, str]] = []
    vm.backtestProgressChanged.connect(
        lambda: seen.append((vm.backtestProgressPercent, vm.backtestProgressText))
    )

    vm.set_backtest_progress(42.0, "Running…")

    assert seen == [(42.0, "Running…")]


def test_the_two_bars_do_not_touch_each_other(qapp) -> None:
    """A sync finishing must not make the run look finished."""
    vm = RunProgressViewModel()
    sync_emits: list[int] = []
    vm.syncProgressChanged.connect(lambda: sync_emits.append(1))

    vm.set_backtest_progress(50.0, "Running…")

    assert vm.syncProgressPercent == IDLE_PERCENT
    assert sync_emits == []


def test_reset_clears_both_the_percent_and_the_caption(qapp) -> None:
    """A 0% bar still captioned "Running…" is worse than no bar."""
    vm = RunProgressViewModel()
    vm.set_backtest_progress(80.0, "Running…")
    vm.set_sync_progress(30.0, "Loading…")

    vm.reset_backtest_progress()
    vm.reset_sync_progress()

    assert (vm.backtestProgressPercent, vm.backtestProgressText) == (
        IDLE_PERCENT,
        IDLE_TEXT,
    )
    assert (vm.syncProgressPercent, vm.syncProgressText) == (IDLE_PERCENT, IDLE_TEXT)
