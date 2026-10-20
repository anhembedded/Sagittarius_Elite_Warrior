"""`EPIC-040B` — the Grid's backtest answers through the kind-neutral port.

@details The replay's numbers are the handler's and the simulator's, untouched: the oracle
(`EPIC-039B`) and the Futures tests (`EPIC-039K`) pin them. What this pins is the mapping: every
field of a `GridBacktestResult` lands in the outcome or in its `detail`, over the oracle's own 80
replays; the missing funding is the first note; and a refusal or a cancellation keeps what the
screen acts on."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    GridKindBacktester,
    outcome_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestAnswer,
    GridBacktestRefusal,
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestCancelled,
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    FundingSchedule,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestCancelled,
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_summary import (
    summary_of,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    BRACKETS,
    bar,
    position_config,
    replay,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.spot_oracle.corpus import (
    MINUTE,
    SIMULATION_CASES,
    simulation_cases,
)

_T0 = datetime(2026, 9, 1, tzinfo=UTC)
_SYMBOL = "BTCUSDT"
_VENUE = TradingVenue.SPOT_TESTNET


def _replayed(index: int) -> GridBacktestResult:
    case = simulation_cases()[index]
    result = simulate_grid(
        GridBacktestInputs(
            GridParams.from_config(case.config), case.terms, case.bars, MINUTE
        )
    )
    assert isinstance(result, GridBacktestResult)
    return result


@pytest.mark.parametrize("index", range(SIMULATION_CASES))
def test_every_field_of_a_replay_lands_in_the_outcome_or_its_detail(index: int) -> None:
    result = _replayed(index)

    outcome = outcome_of(result)

    assert outcome.detail is result
    assert [(b.time, b.open, b.high, b.low, b.close) for b in outcome.bars] == [
        (b.time, b.open, b.high, b.low, b.close) for b in result.bars
    ]
    assert [(p.time, p.bot, p.benchmark) for p in outcome.equity] == [
        (p.time, p.grid, p.buy_and_hold) for p in result.equity
    ]
    assert [
        (f.time, f.side, f.price, f.quantity, f.fee_quote, f.label, f.maker)
        for f in outcome.fills
    ] == [
        (f.time, f.side, f.price, f.quantity, f.fee_quote, f.label, f.maker)
        for f in result.fills
    ]
    assert (outcome.maker_fees, outcome.taker_fees) == (
        result.maker_fees,
        result.taker_fees,
    )
    provenance = outcome.provenance
    assert (
        provenance.config,
        provenance.maker_fee,
        provenance.taker_fee,
        provenance.first_candle,
        provenance.last_candle,
        provenance.fill_rule,
        provenance.window,
    ) == (
        result.provenance.config,
        result.provenance.maker_fee,
        result.provenance.taker_fee,
        result.provenance.first_candle,
        result.provenance.last_candle,
        result.provenance.fill_rule,
        result.provenance.window,
    )


def test_the_outcome_shows_the_figures_and_notes_the_grid_page_shows() -> None:
    result = _replayed(0)

    outcome = outcome_of(result)
    summary = summary_of(result)

    assert [f.key for f in outcome.figures] == [s.key for s in summary.readout.specs]
    assert [f.title for f in outcome.figures] == [
        s.title for s in summary.readout.specs
    ]
    assert {f.key: f.value for f in outcome.figures} == dict(summary.readout.values)
    assert outcome.notes == summary.notes


def test_the_missing_funding_is_the_first_note_of_a_futures_outcome() -> None:
    no_funding = FundingSchedule(
        (), False, "FUNDING IS NOT INCLUDED in this result: the exchange is down."
    )
    result = replay(
        [bar(0, "65000", "65200", "64800", "65000")],
        position_config("LONG"),
        funding=no_funding,
    )

    outcome = outcome_of(result)

    assert outcome.notes[0].startswith("FUNDING IS NOT INCLUDED")
    assert "funding_paid" in [f.key for f in outcome.figures]


class _Scripted(IQueryHandler[RunGridBacktestQuery, GridBacktestAnswer]):
    def __init__(self, answer: GridBacktestAnswer) -> None:
        self._answer = answer
        self.queries: list[RunGridBacktestQuery] = []

    def execute(self, query: RunGridBacktestQuery) -> GridBacktestAnswer:
        self.queries.append(query)
        return self._answer


def _request(**changes: object) -> KindBacktestRequest:
    fields: dict[str, object] = {
        "symbol": _SYMBOL,
        "config": CONFIG,
        "terms": TERMS,
        "interval": TimeFrame.FIFTEEN_MINUTES,
        "start": _T0,
        "end": _T0 + timedelta(hours=6),
        "venue": _VENUE,
        **changes,
    }
    return KindBacktestRequest(**fields)  # type: ignore[arg-type]


def test_a_refusal_keeps_what_the_screen_acts_on() -> None:
    refusal = GridBacktestRefusal("no funding", funding_unavailable=True)

    answer = GridKindBacktester(_Scripted(refusal)).run(_request())

    assert answer == BacktestRefusal("no funding", False, True)


def test_a_cancelled_replay_is_a_value() -> None:
    answer = GridKindBacktester(_Scripted(GridBacktestCancelled(3, 24))).run(_request())

    assert answer == BacktestCancelled(3, 24)


def test_the_request_reaches_the_query_whole_and_the_warm_up_is_ignored() -> None:
    handler = _Scripted(GridBacktestRefusal("x"))
    never = lambda: False

    GridKindBacktester(handler).run(
        _request(
            warmup=timedelta(hours=9),
            funding=FundingRequirement.OPTIONAL,
            cancelled=never,
            brackets=BRACKETS,
        )
    )

    query = handler.queries[0]
    assert (query.symbol, query.interval, query.start, query.end, query.venue) == (
        _SYMBOL,
        TimeFrame.FIFTEEN_MINUTES,
        _T0,
        _T0 + timedelta(hours=6),
        _VENUE,
    )
    assert query.funding is FundingRequirement.OPTIONAL
    assert query.cancelled is never
    assert query.terms == TERMS
    assert query.brackets is BRACKETS
    assert dict(query.config) == dict(CONFIG)


def _stored(count: int) -> FakeMarketDataRepository:
    repository = FakeMarketDataRepository()
    candles = []
    for n in range(count):
        at = _T0 + timedelta(minutes=15 * n)
        close = 65000.0 + (200 if n % 2 else -200)
        candles.append(
            MarketData(
                symbol=_SYMBOL,
                interval=TimeFrame.FIFTEEN_MINUTES.value,
                open_time=at,
                open_price=65000.0,
                high_price=max(65000.0, close) + 5,
                low_price=min(65000.0, close) - 5,
                close_price=close,
                volume=1.0,
                close_time=at + timedelta(minutes=15),
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.5,
                taker_buy_quote_asset_volume=0.5,
            )
        )
    repository.save_klines(MarketType.SPOT, candles)
    return repository


def _real(repository: FakeMarketDataRepository) -> GridKindBacktester:
    return GridKindBacktester(
        RunGridBacktestQueryHandler(
            FakeMarketDataSources().serving(
                FakeMarketDataSources.ports(
                    _VENUE.market_data_venue,
                    history=StoredKlinesReader(repository),
                    repository=repository,
                )
            )
        )
    )


def test_stored_candles_are_replayed_into_an_outcome() -> None:
    answer = _real(_stored(24)).run(_request())

    assert isinstance(answer, BacktestOutcome)
    assert isinstance(answer.detail, GridBacktestResult)
    assert len(answer.bars) == 24
    assert answer.provenance.window is not None


def test_a_period_partly_stored_keeps_its_window_field_by_field() -> None:
    """The window says how much of the period was stored; a swapped count would turn the
    "N of M candles stored" line and the sync offer around."""
    answer = _real(_stored(12)).run(_request())

    assert isinstance(answer, BacktestOutcome)
    assert isinstance(answer.detail, GridBacktestResult)
    window = answer.provenance.window
    source = answer.detail.provenance.window
    assert window is not None and source is not None
    assert (window.start, window.end) == (source.start, source.end)
    assert (window.expected_candles, window.stored_candles) == (24, 12)
    assert window.missing_candles == 12


@pytest.mark.parametrize("reason", list(StopReason), ids=lambda r: r.value)
def test_every_way_a_grid_replay_stops_has_a_neutral_cause(reason: StopReason) -> None:
    result = dataclasses.replace(
        _replayed(0), stop_reason=reason, stop_detail="the detail"
    )

    outcome = outcome_of(result)

    assert outcome.stop.value == reason.value
    assert outcome.stop_detail == "the detail"


def test_a_period_with_nothing_stored_is_refused_with_the_sync_flag() -> None:
    answer = _real(FakeMarketDataRepository()).run(_request())

    assert isinstance(answer, BacktestRefusal)
    assert answer.missing_candles
    assert f"No 15m candles of {_SYMBOL}" in answer.reason


def test_a_run_cancelled_before_it_starts_answers_cancelled() -> None:
    answer = _real(_stored(24)).run(_request(cancelled=lambda: True))

    assert isinstance(answer, BacktestCancelled)
    assert answer.total_bars == 24
