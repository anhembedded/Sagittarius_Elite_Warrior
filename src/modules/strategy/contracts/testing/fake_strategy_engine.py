"""The verified fake for `IStrategyEngine` / `IStrategyEngineFactory` (HLD §10.3).

**Who needs it.** Both backtest handlers drive an engine, and this is a *foreign*
port to them — `Mock(spec=IStrategyEngine)` is refused by
`test_no_foreign_port_is_mocked.py`, and `CS-001` is what a loose stand-in cost
this repository already.

**Scripted decisions, and the asymmetry kept.** A test says which signal comes
back on which candle index. What this fake will **not** do is let the two tick
methods behave identically: `on_tick()` commits (each candle is consumed once and
the index advances) while `on_forming_bar_tick()` peeks (the index does not move,
and the same forming bar may be asked about any number of times). That difference
is `BOT-042D`'s whole point and the one promise `IStrategyEngine`'s docstring
says a consumer must not flatten — a fake that treated them the same would let a
handler conflate them and still pass.

**It refuses a candle the real engine would refuse.** `on_forming_bar_tick()`
raises on a closed candle, exactly as `StrategyEngine` does, because a handler
that sent the wrong kind would corrupt indicator state in production and a
permissive fake is how that ships green.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_engine import (
    IStrategyEngine,
    IStrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


class FakeStrategyEngine(IStrategyEngine):
    """An engine whose decisions a test writes down in advance."""

    def __init__(self, decisions: Sequence[Signal | None] = ()) -> None:
        #: One entry per **closed** candle, in order. Past the end: `None`,
        #: which is what a real strategy that holds forever also answers.
        self._decisions = list(decisions)
        #: How many closed candles have been committed. `on_forming_bar_tick()`
        #: never advances it — that is the asymmetry this fake exists to keep.
        self.committed = 0
        #: Every `(candle, position_side)` the engine was asked about, closed and
        #: forming alike, so a test can assert *what* was fed as well as how much.
        self.seen: list[tuple[MarketData, PositionSide | None]] = []

    def on_tick(
        self,
        candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        self.seen.append((candle, current_position_side))
        index = self.committed
        self.committed += 1
        return self._decisions[index] if index < len(self._decisions) else None

    def on_forming_bar_tick(
        self,
        forming_candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        if forming_candle.is_closed:
            raise ValueError(
                "on_forming_bar_tick() requires an open (is_closed=False) "
                "candle — a closed candle belongs on on_tick()."
            )
        self.seen.append((forming_candle, current_position_side))
        index = self.committed
        return self._decisions[index] if index < len(self._decisions) else None


class FakeStrategyEngineFactory(IStrategyEngineFactory):
    """Hands out `FakeStrategyEngine`s and records what was asked for."""

    def __init__(self, decisions: Sequence[Signal | None] = ()) -> None:
        self._decisions = list(decisions)
        #: Every `(key, params)` a consumer asked to build, in order.
        self.built: list[tuple[str, Mapping[str, Any] | None]] = []
        #: The engines handed out, so a test can read what its subject drove.
        self.engines: list[FakeStrategyEngine] = []
        #: Keys this factory refuses, so a consumer's error path is reachable.
        self.unknown_keys: set[str] = set()

    def refuses(self, strategy_key: str) -> None:
        """Script a key the registry does not know."""
        self.unknown_keys.add(strategy_key)

    def build(
        self, strategy_key: str, params: Mapping[str, Any] | None = None
    ) -> IStrategyEngine:
        if strategy_key in self.unknown_keys:
            # The registry's own error, unwrapped — the port promises exactly
            # this, and a fake that raised something else would let a consumer
            # catch the wrong thing and still pass.
            raise KeyError(f"No strategy registered under key {strategy_key!r}")
        self.built.append((strategy_key, params))
        engine = FakeStrategyEngine(self._decisions)
        self.engines.append(engine)
        return engine
