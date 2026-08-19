from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.scripting import (
    DEFAULT_HISTORY,
    InputDeclarations,
    InputKind,
    ScriptInput,
    Series,
    build_input,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_HOLD_REASON = "no signal"


class BaseStrategy(ABC):
    """
    @brief Base class for concrete IStrategy implementations.
    @details Gathers what every strategy repeats: tracking bar-to-bar history
    of already-computed indicator values (via `Series`, mirrored from
    `domain/scripting/`) so `decide()` can detect crosses, and turning a bare
    `(SignalAction, reason, metadata)` decision into the full `Signal` the
    engine expects. A strategy never computes its own indicators —
    `StrategyEngine` owns that so batch and incremental runs stay identical —
    so `build_indicators()` only *describes* what it needs.

    Subclasses that need configurable parameters (BOT-046) override `setup()`
    and call `self.input_*()` there — the same declare-and-resolve mechanism
    `BaseIndicatorScript` uses (BOT-044), reused via `domain/scripting/`
    rather than shared through inheritance: the two base classes stay
    deliberately separate (a strategy consumes pre-computed indicator values
    and makes one decision per bar; a script computes its own values and
    draws several kinds of output), but both need the same "describe a
    parameter, get its resolved value" primitive.
    """

    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        self._series: dict[str, Series] = {}
        self._inputs = InputDeclarations(dict(params) if params else None)

        self.setup()

        # Caught only after setup(), once every declaration has been made —
        # see BaseIndicatorScript.__init__ for the identical reasoning.
        unused = self._inputs.unused_param_names()
        if unused:
            raise ValueError(
                f"{type(self).__name__} got param(s) it never declares: {list(unused)}"
            )

    def setup(self) -> None:
        """Override to declare this strategy's parameters via `input_*()`.
        Runs once per instance, before `build_indicators()`/`decide()` are
        ever called. The default does nothing — a strategy with nothing to
        configure needs no override."""

    @property
    def inputs(self) -> tuple[ScriptInput, ...]:
        """What this strategy declares about its own parameters, in the
        order `setup()` declared them. Empty for a strategy that declares
        none."""
        return self._inputs.declared

    # ------------------------------------------------------------------ #
    # Parameter declaration — call these from setup(). Each records the
    # declaration (so a UI can build a form, BOT-047) AND returns the value
    # to use, mirroring BaseIndicatorScript's input_*() (BOT-044).
    # ------------------------------------------------------------------ #

    def input_int(
        self,
        name: str,
        default: int,
        *,
        label: str | None = None,
        minval: int | None = None,
        maxval: int | None = None,
        group: str | None = None,
        suffix: str | None = None,
        step: float | None = None,
    ) -> int:
        return self._inputs.declare(
            build_input(
                InputKind.INT,
                name,
                default,
                label,
                minval,
                maxval,
                None,
                group,
                suffix,
                step,
            )
        )

    def input_float(
        self,
        name: str,
        default: float,
        *,
        label: str | None = None,
        minval: float | None = None,
        maxval: float | None = None,
        group: str | None = None,
        suffix: str | None = None,
        step: float | None = None,
    ) -> float:
        return self._inputs.declare(
            build_input(
                InputKind.FLOAT,
                name,
                default,
                label,
                minval,
                maxval,
                None,
                group,
                suffix,
                step,
            )
        )

    def input_bool(
        self,
        name: str,
        default: bool,
        *,
        label: str | None = None,
        group: str | None = None,
    ) -> bool:
        return self._inputs.declare(
            build_input(InputKind.BOOL, name, default, label, group=group)
        )

    def input_string(
        self,
        name: str,
        default: str,
        *,
        options: Sequence[str] | None = None,
        label: str | None = None,
        group: str | None = None,
    ) -> str:
        return self._inputs.declare(
            build_input(
                InputKind.STRING, name, default, label, options=options, group=group
            )
        )

    def evaluate(self, context: StrategyContext) -> Signal:
        action, reason, metadata = self.decide(context)
        candle = context.candle
        return Signal(
            symbol=candle.symbol,
            action=action,
            reason=reason,
            price=candle.close_price,
            time=candle.close_time,
            metadata=metadata,
        )

    @abstractmethod
    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]: ...

    @abstractmethod
    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        """The named `IIndicator` instances `StrategyEngine` should own and
        feed this strategy — the same names `decide()` reads from
        `context.indicators`."""
        ...

    def series(self, key: str, history: int = DEFAULT_HISTORY) -> Series:
        return self._series.setdefault(key, Series(history))

    def track(
        self, series: Series, value: float | None, context: StrategyContext
    ) -> float | None:
        """Records `value` into `series` the way `context.candle` calls for
        (BOT-042D): permanently via `push()` when the candle is closed, or as
        this bar's tentative reading via `poke_provisional()` while it's
        still forming (`context.candle.is_closed` is `False`). Concrete
        strategies call this instead of `series.push()` directly so
        `decide()` works unmodified whether `StrategyEngine` reached it via
        `on_tick()` (bar close) or `on_forming_bar_tick()` (mid-bar tick) —
        calling this any number of times before the bar closes never
        advances `series`'s committed history (BOT-042C)."""
        if context.candle.is_closed:
            return series.push(value)
        return series.poke_provisional(value)

    def buy(
        self, reason: str, **metadata: Any
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return SignalAction.BUY, reason, metadata

    def sell(
        self, reason: str, **metadata: Any
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return SignalAction.SELL, reason, metadata

    def hold(
        self, reason: str = _HOLD_REASON, **metadata: Any
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return SignalAction.HOLD, reason, metadata
