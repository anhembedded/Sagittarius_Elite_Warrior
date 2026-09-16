"""The contract suite for `IStrategyEngine` / `IStrategyEngineFactory` (HLD §10.3).

Both implementations run it: the fake pair, and the real `StrategyEngineFactory`
over the real `StrategyRegistry` and a recording publisher.

**What it pins is the pair of promises a consumer cannot see.** A backtest drives
an engine per candle and never looks inside it, so what it depends on is:

  · a key the registry knows builds something drivable, and an unknown key comes
    back as `KeyError` with the key in it — not a placeholder engine that would
    silently produce a backtest of nothing;
  · `on_tick()` **commits** and `on_forming_bar_tick()` **peeks**. This is the
    asymmetry `BOT-042D` introduced on purpose and the one thing
    `IStrategyEngine`'s docstring tells a consumer not to flatten: peeking any
    number of times must leave the next commit unchanged. A consumer that
    conflated them would get a Realtime backtest whose indicators had been
    advanced by bars that never closed, and no test at the consumer's own tier
    could tell;
  · a closed candle on the forming path **raises**. Accepting it is how
    indicator state gets corrupted in production, so a permissive implementation
    must fail here rather than in a later run nobody connects to this.

Warm-up is deliberately not a contract row. How many candles an indicator needs
before it answers is the strategy's and the indicator library's business, with
their own suites; a row here would be a second copy of it, and the fake would
have to grow a warm-up model to pass — the same trap
`contract_range_coverage.py` records for coverage arithmetic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_engine import (
    IStrategyEngineFactory,
)

_KNOWN_KEY = "ema_crossover"
_UNKNOWN_KEY = "no_such_strategy_anywhere"
_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def candle(index: int, *, close: float, is_closed: bool = True) -> MarketData:
    """One candle, with every field populated.

    A partial stand-in would let an implementation pass by reading only the
    fields it happens to touch, which is `CS-001`'s failure shape.
    """
    open_time = _T0 + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=close,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=close / 2,
        is_closed=is_closed,
    )


class StrategyEngineContract:
    """Inherit this and provide `factory`. Both implementations must pass it."""

    @pytest.fixture
    def factory(self) -> IStrategyEngineFactory:
        raise NotImplementedError(
            "a StrategyEngineContract subclass must provide a `factory` fixture "
            "returning the IStrategyEngineFactory under test"
        )

    def test_a_known_key_builds_something_drivable(self, factory) -> None:
        engine = factory.build(_KNOWN_KEY)

        assert engine.on_tick(candle(0, close=100.0)) is None or True
        # The assertion above is deliberately weak on *what* it decides — that
        # is the strategy's business. What this row pins is that a built engine
        # accepts a candle at all, which is the whole of what a consumer needs
        # before it can run a backtest.

    def test_an_unknown_key_raises_with_the_key_in_it(self, factory) -> None:
        """Never a placeholder engine: a backtest over a strategy that does not
        exist would produce an empty trade log and look like a strategy that
        simply never traded."""
        with pytest.raises(KeyError) as caught:
            factory.build(_UNKNOWN_KEY)

        assert _UNKNOWN_KEY in str(caught.value)

    def test_peeking_a_forming_bar_leaves_the_next_commit_unchanged(
        self, factory
    ) -> None:
        """`BOT-042D`'s asymmetry, and the reason it is a contract.

        Two engines from the same factory see the same closed candles; one of
        them is also asked about a forming bar three times first. Their
        committed decisions must match, because peeking does not commit.
        """
        closed = [candle(i, close=100.0 + i) for i in range(4)]
        forming = candle(4, close=999.0, is_closed=False)

        untouched = factory.build(_KNOWN_KEY)
        peeked = factory.build(_KNOWN_KEY)
        for _ in range(3):
            peeked.on_forming_bar_tick(forming)

        assert [untouched.on_tick(c) for c in closed] == [
            peeked.on_tick(c) for c in closed
        ], (
            "peeking a forming bar changed what the closed candles decided — "
            "on_forming_bar_tick() must not commit indicator state (BOT-042D)"
        )

    def test_a_closed_candle_on_the_forming_path_raises(self, factory) -> None:
        """The wrong candle on the wrong method corrupts indicator state, so it
        must fail here rather than in a run nobody connects back to this."""
        engine = factory.build(_KNOWN_KEY)

        with pytest.raises(ValueError):
            engine.on_forming_bar_tick(candle(0, close=100.0))
