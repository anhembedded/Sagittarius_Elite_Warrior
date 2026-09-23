"""`EPIC-003F5b` — `RunResultViewModel` on its own."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.run_result_view_model import (
    RunResultViewModel,
)


def test_a_fresh_view_model_reports_no_result_rather_than_a_blank_one(qapp) -> None:
    """Every widget hides its row on the empty value, so "nothing yet" and
    "a run that produced nothing" must look the same on purpose."""
    vm = RunResultViewModel()

    assert vm.resultText == ""
    assert vm.resultIsError is False
    assert vm.primaryStatCards == []
    assert vm.extendedStatCards == []
    assert vm.extended_metrics_snapshot() is None
    assert vm.resultWarningText == ""
    assert vm.limitations == []
    assert vm.needsDataSync is False
    assert vm.drawdownPoints == []
    assert vm.yearlyReturns == []


def test_result_text_and_error_flag_change_on_one_emit(qapp) -> None:
    vm = RunResultViewModel()
    seen: list[tuple[str, bool]] = []
    vm.resultChanged.connect(lambda: seen.append((vm.resultText, vm.resultIsError)))

    vm.set_result("No data found", True)

    assert seen == [("No data found", True)]


def test_clearing_the_cards_is_a_single_call_for_both_lists(qapp) -> None:
    vm = RunResultViewModel()
    vm.set_stat_cards([{"label": "PnL"}], [{"label": "Sharpe"}])

    vm.set_stat_cards([], [])

    assert vm.primaryStatCards == []
    assert vm.extendedStatCards == []


def test_limitations_are_copied_not_aliased(qapp) -> None:
    """The caller builds this list while formatting a result; holding a
    reference would let a later `.append()` change what the screen shows
    without any signal."""
    vm = RunResultViewModel()
    source = ["Does not simulate funding fees"]

    vm.set_limitations(source)
    source.append("added after set")

    assert vm.limitations == ["Does not simulate funding fees"]


def test_the_warning_line_only_emits_when_it_actually_changes(qapp) -> None:
    vm = RunResultViewModel()
    seen: list[int] = []
    vm.resultWarningTextChanged.connect(lambda: seen.append(1))

    vm.set_result_warning_text("Data is missing 3 candles")
    vm.set_result_warning_text("Data is missing 3 candles")

    assert len(seen) == 1


def test_the_coverage_banner_reads_both_of_its_halves_from_here(qapp) -> None:
    """`backtest_top_panel.py` shows the banner on
    `needsDataSync and dataCoverageMessage != ""` — the two halves live
    together so the banner cannot be left half-stale."""
    vm = RunResultViewModel()

    vm.set_data_coverage(False, "Only have data from 2024-01-01")
    vm.set_needs_data_sync(True)

    assert vm.isDataFullyCovered is False
    assert bool(vm.needsDataSync) and vm.dataCoverageMessage != ""


def test_drawdown_points_change_on_set_and_clear(qapp) -> None:
    vm = RunResultViewModel()
    seen: list[int] = []
    vm.drawdownPointsChanged.connect(lambda: seen.append(1))
    points = [{"t": 0.0, "v": -1.5}]

    vm.set_drawdown_points(points)

    assert vm.drawdownPoints == points
    assert len(seen) == 1

    vm.set_drawdown_points([])

    assert vm.drawdownPoints == []
    assert len(seen) == 2


def test_yearly_returns_change_on_set_and_clear(qapp) -> None:
    vm = RunResultViewModel()
    seen: list[int] = []
    vm.yearlyReturnsChanged.connect(lambda: seen.append(1))
    rows = [{"year": 2024, "months": [None] * 12, "ytdText": "+0.00%"}]

    vm.set_yearly_returns(rows)

    assert vm.yearlyReturns == rows
    assert len(seen) == 1

    vm.set_yearly_returns([])

    assert vm.yearlyReturns == []
    assert len(seen) == 2
