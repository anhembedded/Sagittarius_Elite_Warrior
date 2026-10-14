"""`EPIC-039J` — a Futures backtest on the screen: the brackets, the market, and the explicit
choice to run without funding (`EPIC-039K`, decision O9).

@details The business promise: a Futures period whose funding history cannot be read is
refused first, in words; only the user's click replays it without funding, and that run is
the one the application is told is OPTIONAL. Run waits for the brackets a liquidation price
needs, and Spot is never offered the choice."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.result import (
    GridBacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest import (
    GridBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .grid_backtest_fixtures import SYMBOL, HeldPool, context

_BRACKETS = LeverageBrackets(
    SYMBOL,
    (
        LeverageBracket(
            1, 125, Decimal(0), Decimal(10**7), Decimal("0.004"), Decimal(0)
        ),
    ),
)
_NO_FUNDING = GridBacktestRefusal(
    "The funding history of BTCUSDT could not be read.", funding_unavailable=True
)


class _Scripted(ICommandDispatcher):
    """Answers each backtest with the next canned answer and keeps what it was asked."""

    def __init__(self, *answers: object) -> None:
        self._answers = list(answers)
        self.queries: list[RunGridBacktestQuery] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any:
        assert isinstance(input_dto, RunGridBacktestQuery)
        self.queries.append(input_dto)
        return self._answers.pop(0)


def _world(
    dispatcher: _Scripted, market: MarketType
) -> tuple[GridBacktest, HeldPool, Any]:
    repository = FakeMarketDataRepository()
    sync = FakeMarketDataSync()
    pool = HeldPool()
    feed = MarketDataCandleFeed(
        sync, StoredKlinesReader(repository), FakeMarketStream(), market
    )
    backtest = GridBacktest(
        BacktestPorts(pool, dispatcher, sync, feed, RecordingNotifier(), market)
    )
    return backtest, pool, sync


def _futures_context(brackets: LeverageBrackets | None = _BRACKETS):  # type: ignore[no-untyped-def]
    return replace(context(), venue=TradingVenue.FUTURES_TESTNET, brackets=brackets)


def test_run_waits_for_the_brackets_a_liquidation_price_needs(qtbot: Any) -> None:
    backtest, _pool, _sync = _world(_Scripted(), MarketType.FUTURES_USD_M)
    qtbot.addWidget(backtest.view)

    backtest.follow(_futures_context(brackets=None))

    assert not backtest.view.run_button.isEnabled()
    assert "leverage brackets" in backtest.view.run_button.toolTip()


def test_a_spot_backtest_does_not_wait_for_brackets(qtbot: Any) -> None:
    backtest, _pool, _sync = _world(_Scripted(), MarketType.SPOT)
    qtbot.addWidget(backtest.view)

    backtest.follow(context())

    assert backtest.view.run_button.isEnabled()


def test_missing_funding_is_refused_first_and_only_a_click_runs_without_it(
    qtbot: Any,
) -> None:
    dispatcher = _Scripted(_NO_FUNDING, _NO_FUNDING)
    backtest, pool, _sync = _world(dispatcher, MarketType.FUTURES_USD_M)
    view = backtest.view
    qtbot.addWidget(view)
    backtest.follow(_futures_context())

    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    pool.run_all()

    assert dispatcher.queries[0].funding is FundingRequirement.REQUIRED
    assert dispatcher.queries[0].brackets == _BRACKETS
    assert view.no_funding_button.isVisibleTo(view)
    assert "funding" in view.status.text().lower()
    assert len(dispatcher.queries) == 1

    qtbot.mouseClick(view.no_funding_button, Qt.MouseButton.LeftButton)
    pool.run_all()

    assert [q.funding for q in dispatcher.queries] == [
        FundingRequirement.REQUIRED,
        FundingRequirement.OPTIONAL,
    ]
    backtest.shutdown()


def test_another_refusal_does_not_offer_to_skip_funding(qtbot: Any) -> None:
    dispatcher = _Scripted(GridBacktestRefusal("The period must hold candles."))
    backtest, pool, _sync = _world(dispatcher, MarketType.FUTURES_USD_M)
    view = backtest.view
    qtbot.addWidget(view)
    backtest.follow(_futures_context())

    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    pool.run_all()

    assert not view.no_funding_button.isVisibleTo(view)
    backtest.shutdown()


def test_a_syncs_request_is_in_the_venues_market(qtbot: Any) -> None:
    dispatcher = _Scripted(
        GridBacktestRefusal("No 15m candles stored.", missing_candles=True)
    )
    backtest, pool, sync = _world(dispatcher, MarketType.FUTURES_USD_M)
    view = backtest.view
    qtbot.addWidget(view)
    backtest.follow(_futures_context())
    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    pool.run_all()

    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)
    pool.run_all()

    assert {request.market for request in sync.requests} == {MarketType.FUTURES_USD_M}
    backtest.shutdown()
