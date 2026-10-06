"""`EPIC-033K`/`EPIC-033N` — a Grid backtest's figures are a read-out of raw
values by kind, written by the application's formatter; its caveats are
sentences beside them, never a figure's text.

The result is the preview's sample replay (`simulate_grid` over five days
of hourly candles, no 1-second klines), so every figure is what the replay
computed, not a number written here."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    DataWindow,
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    FILL_RULE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_summary import (
    GridSummary,
    summary_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview import (
    sample_result,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


@pytest.fixture(scope="module")
def result() -> GridBacktestResult:
    return sample_result()


def _kinds(summary: GridSummary) -> dict[str, ColumnKind]:
    return {spec.key: spec.kind for spec in summary.readout.specs}


def test_every_figure_is_a_raw_value_of_its_kind(result) -> None:
    summary = summary_of(result)
    values, kinds = summary.readout.values, _kinds(summary)

    assert values["first_candle"] == result.provenance.first_candle
    assert kinds["first_candle"] is ColumnKind.TIMESTAMP
    assert values["candles"] == len(result.bars)
    assert values["grid_end"] == result.equity[-1].grid
    assert kinds["grid_end"] is ColumnKind.MONEY
    assert values["grid_profit"] == result.grid_profit
    assert values["cycles"] == result.completed_cycles
    assert values["unrealised"] == result.unrealised
    assert values["maker_fees"] == result.maker_fees
    assert values["taker_fees"] == result.taker_fees
    assert values["coarse_candles"] == len(result.coarse_periods)
    assert all(isinstance(v, Decimal | int | datetime) for v in values.values())


def test_a_change_is_a_percent_of_the_capital(result) -> None:
    summary = summary_of(result)
    capital = GridParams.from_config(dict(result.provenance.config)).capital_quote
    end = result.equity[-1]

    assert _kinds(summary)["grid_change"] is ColumnKind.PERCENT
    assert summary.readout.values["grid_change"] == (end.grid - capital) / capital * 100
    assert summary.readout.values["hold_change"] == (
        (end.buy_and_hold - capital) / capital * 100
    )


def test_a_fee_rate_is_a_percent(result) -> None:
    summary = summary_of(result)

    assert summary.readout.values["maker_rate"] == result.provenance.maker_fee * 100
    assert _kinds(summary)["taker_rate"] is ColumnKind.PERCENT


def test_the_caveats_are_sentences_beside_the_figures(result) -> None:
    notes = " ".join(summary_of(result).notes)

    assert FILL_RULE in notes
    assert "Stopped by" in notes
    # The sample has no 1-second klines: the order inside a candle is assumed.
    assert "assumed" in notes


def test_a_replay_with_every_second_says_so(result) -> None:
    fine = dataclasses.replace(result, coarse_periods=())

    notes = " ".join(summary_of(fine).notes)

    assert "second by second" in notes
    assert summary_of(fine).readout.values["coarse_candles"] == 0


def test_why_it_stopped_follows_the_stop_reason(result) -> None:
    stopped = dataclasses.replace(
        result, stop_reason=StopReason.STOP_LOSS, stop_detail="price 61,000"
    )

    notes = summary_of(stopped).notes

    assert any("stop loss" in note and "price 61,000" in note for note in notes)


def test_a_period_asked_for_shows_how_much_was_stored(result) -> None:
    window = DataWindow(
        start=datetime(2026, 9, 28, tzinfo=UTC),
        end=datetime(2026, 10, 3, tzinfo=UTC),
        expected_candles=120,
        stored_candles=100,
    )
    asked = dataclasses.replace(
        result, provenance=dataclasses.replace(result.provenance, window=window)
    )

    summary = summary_of(asked)

    assert summary.readout.values["stored_candles"] == 100
    assert summary.readout.values["expected_candles"] == 120
    assert summary.readout.values["asked_from"] == window.start
    assert any("not the whole period" in note for note in summary.notes)
    assert "stored_candles" not in summary_of(result).readout.values


def test_a_whole_period_stored_has_no_missing_caveat(result) -> None:
    window = DataWindow(
        start=datetime(2026, 9, 28, tzinfo=UTC),
        end=datetime(2026, 10, 3, tzinfo=UTC),
        expected_candles=120,
        stored_candles=120,
    )
    whole = dataclasses.replace(
        result, provenance=dataclasses.replace(result.provenance, window=window)
    )

    assert not any("not the whole period" in note for note in summary_of(whole).notes)
