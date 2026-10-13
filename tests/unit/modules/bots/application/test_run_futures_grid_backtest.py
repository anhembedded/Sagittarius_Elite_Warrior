"""`EPIC-039K` — the Grid backtest on a Futures venue: its market's candles, the symbol's
brackets, the funding settled in the period, and a refusal in words for each thing missing.

The candles and the funding history are fakes of the market-data ports (recorded-shape data,
nothing read from an exchange): the venue under test is the Futures **testnet**, so every read
must go to `FUTURES_TESTNET`'s ports and to the Futures shard of its store.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestRefusal,
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.cost_model_futures import (
    FuturesCostModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.futures_backtest_terms import (
    futures_run_terms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    FUNDING_INTERVAL,
    FundingView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    no_funding,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestCancelled,
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_funding_history import (
    FakeFundingHistory,
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
    MAKER,
    TAKER,
    position_config,
    schedule,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
)

D = Decimal
T0 = datetime(2026, 9, 1, tzinfo=UTC)
SYMBOL = "BTCUSDT"
VENUE = TradingVenue.FUTURES_TESTNET
_FEES = replace(TERMS, maker_fee=MAKER, taker_fee=TAKER)


def _minute(n: int, ohlc: tuple[float, float, float, float]) -> MarketData:
    o, h, low, c = ohlc
    at = T0 + timedelta(minutes=n)
    return MarketData(
        symbol=SYMBOL,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=at,
        open_price=o,
        high_price=h,
        low_price=low,
        close_price=c,
        volume=1.0,
        close_time=at + timedelta(minutes=1),
        quote_asset_volume=1.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=0.5,
    )


_QUIET = (65000.0, 65200.0, 64800.0, 65000.0)


def _futures_candles() -> FakeMarketDataRepository:
    repository = FakeMarketDataRepository()
    repository.save_klines(
        MarketType.FUTURES_USD_M, [_minute(n, _QUIET) for n in range(4)]
    )
    return repository


def _handler(
    repository: FakeMarketDataRepository, funding: FakeFundingHistory
) -> tuple[RunGridBacktestQueryHandler, FakeMarketDataSources]:
    sources = FakeMarketDataSources().serving(
        FakeMarketDataSources.ports(
            VENUE.market_data_venue,
            history=StoredKlinesReader(repository),
            repository=repository,
            funding=funding,
        )
    )
    return RunGridBacktestQueryHandler(sources), sources


def _query(**changes: object) -> RunGridBacktestQuery:
    fields: dict[str, object] = {
        "symbol": SYMBOL,
        "config": position_config("LONG"),
        "terms": _FEES,
        "interval": TimeFrame.ONE_MINUTE,
        "start": T0,
        "end": T0 + timedelta(minutes=10),
        "venue": VENUE,
        "brackets": BRACKETS,
        **changes,
    }
    return RunGridBacktestQuery(**fields)  # type: ignore[arg-type]


def _event(minute: int, rate: str = "0.0001", mark: str = "65000") -> FundingEvent:
    return FundingEvent(SYMBOL, T0 + timedelta(minutes=minute), D(rate), D(mark))


def _run(
    history: FakeFundingHistory | None = None, **changes: object
) -> GridBacktestResult:
    handler, _ = _handler(_futures_candles(), history or FakeFundingHistory())
    answer = handler.execute(_query(**changes))
    assert isinstance(answer, GridBacktestResult), answer
    return answer


def _refusal(
    history: FakeFundingHistory | None = None, **changes: object
) -> GridBacktestRefusal:
    handler, _ = _handler(_futures_candles(), history or FakeFundingHistory())
    answer = handler.execute(_query(**changes))
    assert isinstance(answer, GridBacktestRefusal), answer
    return answer


# -- the market ---------------------------------------------------------------- #


def test_a_futures_backtest_reads_the_futures_candles_of_the_venues_market_data_venue() -> (
    None
):
    handler, sources = _handler(_futures_candles(), FakeFundingHistory())

    answer = handler.execute(_query())

    assert isinstance(answer, GridBacktestResult)
    assert sources.asked == [VENUE.market_data_venue]
    assert [b.close for b in answer.bars] == [D(65000)] * 4
    assert answer.futures is not None


def test_spot_candles_are_not_futures_candles_and_a_missing_history_is_refused() -> (
    None
):
    spot_only = FakeMarketDataRepository()
    spot_only.save_klines(MarketType.SPOT, [_minute(n, _QUIET) for n in range(4)])
    handler, _ = _handler(spot_only, FakeFundingHistory())

    answer = handler.execute(_query())

    assert isinstance(answer, GridBacktestRefusal)
    assert answer.missing_candles
    assert SYMBOL in answer.reason


def test_a_position_venue_allows_a_short_and_a_leverage_a_spot_plan_would_be_refused() -> (
    None
):
    result = _run(config=position_config("SHORT", leverage=8))

    assert result.futures is not None
    assert result.futures.leverage == 8
    assert result.futures.final_position < 0


# -- brackets -------------------------------------------------------------------- #


def test_a_futures_backtest_without_brackets_is_refused_in_words() -> None:
    refusal = _refusal(brackets=None)

    assert "leverage brackets of BTCUSDT were not read" in refusal.reason
    assert "liquidation price" in refusal.reason


def test_a_leverage_above_the_symbols_bracket_is_refused() -> None:
    """10,000 at 125x reaches 1,250,000: the third bracket allows 50x."""
    refusal = _refusal(config=position_config("LONG", leverage=125))

    assert "allows 50x" in refusal.reason
    assert "125x is above it" in refusal.reason


# -- funding ----------------------------------------------------------------------- #


def test_the_funding_settled_in_the_period_is_charged_through_the_cost_model() -> None:
    funding = FakeFundingHistory([_event(1, "0.0001"), _event(2, "-0.0003", "64900")])

    result = _run(funding)

    assert result.futures is not None
    held = result.futures.final_position
    model = FuturesCostModel(_FEES, FundingView(D("0.0001")))
    first = model.funding_estimate(held * D(65000), FUNDING_INTERVAL)
    second = FuturesCostModel(_FEES, FundingView(D("-0.0003"))).funding_estimate(
        held * D(64900), FUNDING_INTERVAL
    )
    assert result.futures.funding_paid == first + second
    assert result.futures.funding_included
    assert result.futures.funding_settlements_charged == 2
    assert "2 funding settlements" in result.futures.funding_note
    assert funding.reads[0].market is MarketType.FUTURES_USD_M
    assert (funding.reads[0].start, funding.reads[0].symbol) == (T0, SYMBOL)


def test_a_missing_funding_history_is_refused_by_default_and_says_why() -> None:
    down = FakeFundingHistory(unavailable="The exchange could not be reached.")

    refusal = _refusal(down)

    assert refusal.funding_unavailable
    assert "The exchange could not be reached." in refusal.reason
    assert "flatters a leveraged grid" in refusal.reason


def test_a_missing_funding_history_can_be_replayed_without_and_the_result_says_so() -> (
    None
):
    down = FakeFundingHistory(unavailable="The exchange could not be reached.")

    result = _run(down, funding=FundingRequirement.OPTIONAL)

    assert result.futures is not None
    assert result.futures.funding_included is False
    assert result.futures.funding_note.startswith("FUNDING IS NOT INCLUDED")
    assert "could not be reached" in result.futures.funding_note
    assert result.futures.funding_paid == 0


def test_a_period_with_no_settlement_is_included_with_nothing_charged() -> None:
    result = _run(FakeFundingHistory())

    assert result.futures is not None
    assert result.futures.funding_included
    assert result.futures.funding_settlements_charged == 0
    assert "0 funding settlements" in result.futures.funding_note


def test_a_record_without_a_mark_price_is_named_in_the_note() -> None:
    old = FundingEvent(SYMBOL, T0 + timedelta(minutes=1), D("0.0001"), None)

    result = _run(FakeFundingHistory([old]))

    assert result.futures is not None
    assert "1 carry no mark price" in result.futures.funding_note


def test_cancelling_while_the_funding_history_is_read_is_a_cancelled_run() -> None:
    """The fake ignores the cancellation check, as a real read ends by it: the handler's own
    contract is that a cancelled read is a value, never a half result."""

    class _Cancelling(FakeFundingHistory):
        def funding_between(self, *args: object, **kwargs: object):  # type: ignore[override]
            raise ExchangeRequestCancelledError("cancelled")

    handler, _ = _handler(_futures_candles(), _Cancelling())

    answer = handler.execute(_query(cancelled=lambda: True))

    assert isinstance(answer, GridBacktestCancelled)


# -- the cost model glue ----------------------------------------------------------- #


def test_the_fees_of_a_futures_replay_are_the_cost_models() -> None:
    terms = futures_run_terms(_FEES, BRACKETS, no_funding("none"))

    assert (terms.maker_fee, terms.taker_fee) == FuturesCostModel(
        _FEES, FundingView(None)
    ).fees()


def test_one_settlement_costs_what_the_cost_model_estimates_for_one_interval() -> None:
    terms = futures_run_terms(_FEES, BRACKETS, schedule())

    charged = terms.charge(D("0.4"), D(65000), D("0.0002"))

    expected = FuturesCostModel(_FEES, FundingView(D("0.0002"))).funding_estimate(
        D("0.4") * D(65000), FUNDING_INTERVAL
    )
    assert charged == expected == D("5.2")
