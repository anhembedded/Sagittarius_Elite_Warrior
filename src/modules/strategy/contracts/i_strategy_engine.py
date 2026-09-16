"""Port: *given this candle, what should I do?* (HLD §3.4, `EPIC-025C` §1 item 2).

**Why an interface and not the class.** `EPIC-025C` §1 item 2 reserved
`IStrategyEngineFactory` for `backtesting`, and PR 2.1c is why its answer has to
be a port rather than `StrategyEngine` itself: that pull request built
`IStrategyCatalog`, measured it, and **deleted** it, because a published contract
may not carry `BaseStrategy`. `StrategyEngine` holds an `IStrategy`, a dict of
`IIndicator`s and an `IEventPublisher` — three of this module's internals — so a
consumer that named the class would be importing all of them by reference.

**Two methods, measured rather than mirrored.** `StrategyEngine` has three public
methods; only these two have a caller outside `modules/strategy/` in `src/`:

| Method | Called from outside the module? |
| :--- | :--- |
| `on_tick()` | yes — both backtest handlers |
| `on_forming_bar_tick()` | yes — the historical-tick handler |
| `run_batch()` | **no** — only this module's own tests and `scripts/benchmark.py` |

So `run_batch()` stays intra-module. PR 1.2 left `quote_asset` out of
`ISymbolCatalog` on the same reasoning: publishing what nobody calls is
publishing a promise nobody has asked anyone to keep.

@par The one promise that is not symmetrical, and must not be flattened
`on_tick()` guarantees batch ≡ incremental: the same candles in either mode reach
the same decisions, because both funnel through one commit point.
`on_forming_bar_tick()` **deliberately breaks that** (`BOT-042D`) — it reads each
indicator's provisional value without committing, so it may decide something the
closed bar would not. A consumer that treated the two as interchangeable would be
reading a guarantee that was never offered, which is why they are separate
methods on this port rather than one with a flag.

@par The seam this leaves open
A second engine — `BOT-076`'s tick-driven one — is a second implementation bound
in `composition/port_bindings.py`, with no consumer change. That is the seam
`BOT-023`'s cancellation left behind, and `architecture-rule.md` §7.2.1's rule
applies: it is cut here because there is now a *second consumer* (backtesting),
not in advance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


class IStrategyEngine(ABC):
    """One armed strategy, fed one candle at a time."""

    @abstractmethod
    def on_tick(
        self,
        candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        """@brief Evaluates a **closed** candle and commits the indicators.

        @return The actionable `Signal`, or `None` while indicators are warming
        up and whenever the strategy holds. `None` is a decision, not a failure.
        """

    @abstractmethod
    def on_forming_bar_tick(
        self,
        forming_candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        """@brief Evaluates a bar still **forming**, without committing.

        @details Reads each indicator's provisional value, so calling this any
        number of times leaves `on_tick()`'s next commit unaffected. It may
        legitimately decide something the closed bar would not — see the class
        note above.
        @raise ValueError if `forming_candle.is_closed` is true: that candle
        belongs on `on_tick()`, and silently accepting it would corrupt the
        indicator state this method exists to protect.
        """


class IStrategyEngineFactory(ABC):
    """Builds a ready-to-run engine for a registered strategy key.

    The consumer names a key and its parameters and gets something it can drive.
    Everything else the engine needs — the registry that resolves the key, the
    indicator set the strategy declares, the publisher its signals go out on —
    is this module's business and stays inside it. Before this port, both
    backtest handlers took `StrategyRegistry` in their constructors and passed
    it back into `build_engine()` along with their own `IEventPublisher`: a
    consumer assembling another context's collaborators, which is the
    transitional shape `EPIC-025` exists to retire.
    """

    @abstractmethod
    def build(
        self, strategy_key: str, params: Mapping[str, Any] | None = None
    ) -> IStrategyEngine:
        """@brief An engine running the strategy registered under `strategy_key`.

        @param params Values for the parameters the strategy declares through
        `input_*()` (`BOT-046`). `None` uses every declared default.
        @raise KeyError if no strategy is registered under that key — the
        registry's own error, deliberately not wrapped: a caller that mistypes a
        key needs the key back, not a new exception type to learn.
        """
