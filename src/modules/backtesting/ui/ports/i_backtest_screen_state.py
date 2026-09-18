"""The Backtest screen's mutable state, as one named contract.

@details `EPIC-013C`. The six coordinators used to receive this state as
seventeen separate getter/setter callables — `get_symbol` alone appeared in
four constructors. Each was an unnamed, untyped hole in the coordinator's
API: nothing said what the callable read, what it could return, or whether
two coordinators handed the same one were looking at the same value.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IBacktestScreenState(ABC):
    """
    @brief What the Backtest screen currently holds, readable and (where a
    coordinator legitimately owns the value) writable.

    @details **An `abc.ABC`, not a `Protocol`.** `architecture-rule.md`
    §2.1 makes ABC the default and allows `Protocol` only where inheritance
    is impossible; nothing here touches Qt, so none of the three exemptions
    applies. It also buys the enforcement this layer otherwise lacks:
    `presentation/` is outside the `mypy` gate, and an ABC still fails
    loudly — `TypeError: Can't instantiate abstract class` — the moment an
    implementation falls behind, which a Protocol would not.

    **Read late, never captured.** Every member below is a property that
    resolves at call time. Implementations must not snapshot values at
    construction: `EPIC-003E` made that mistake four times, each time
    because a test replaced an attribute on the presenter *after* the
    coordinators were built and the captured copy silently won.

    **Only genuine state lives here.** Five things that look similar are
    deliberately still separate constructor parameters, because they are
    not values the screen holds:

    - `get_first_chart_card` — must stay a call. `BUG-013`: a cached card
      becomes a `deleteLater()`-ed C++ object after a host rebuild.
    - `next_preview_id` — an action; it mutates a counter and returns it.
    - `get_current_config` — computed from the ViewModel on each call.
    - `effective_data_interval`, `get_market_metadata` — computed, and the
      latter takes an argument.

    Writability follows Interface Segregation (§1 "I"): only the three
    members a coordinator actually assigns have setters.
    """

    # -- Read-only --------------------------------------------------- #

    @property
    @abstractmethod
    def symbol(self) -> str:
        """The symbol every coordinator is currently working on."""

    @property
    @abstractmethod
    def all_trades(self) -> list[Any]:
        """Trades from the most recent run. Rebound wholesale each run."""

    @property
    @abstractmethod
    def active_strategy_lines(self) -> Any:
        """Indicator overlays currently drawn. Mutated in place, not replaced."""

    @property
    @abstractmethod
    def chart_klines_fetch_limit(self) -> int:
        """How many candles a chart fetch asks for."""

    @property
    @abstractmethod
    def active_preview_id(self) -> int:
        """Generation id of the preview whose results are still wanted."""

    # -- Read/write -------------------------------------------------- #

    @property
    @abstractmethod
    def strategy_params(self) -> dict[str, Any] | None:
        """Parameters of the selected strategy, or `None` when unset."""

    @strategy_params.setter
    @abstractmethod
    def strategy_params(self, params: dict[str, Any] | None) -> None: ...

    @property
    @abstractmethod
    def current_raw_klines(self) -> list[Any]:
        """Unmapped candles behind whatever the chart last drew."""

    @current_raw_klines.setter
    @abstractmethod
    def current_raw_klines(self, klines: list[Any]) -> None: ...

    @property
    @abstractmethod
    def chart_script_keys(self) -> list[str]:
        """Keys of the indicator scripts currently enabled on the chart."""

    @chart_script_keys.setter
    @abstractmethod
    def chart_script_keys(self, keys: list[str]) -> None: ...
