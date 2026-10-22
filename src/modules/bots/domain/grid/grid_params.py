"""`EPIC-029C` — the user's Grid parameters, parsed from the bot's definition.

Every field is the user's (the rule of 2026-10-03: the bot computes from the
parameters and judges them, it never fixes them to a number). No field has a
hidden default: a missing key is an error naming the key, so a definition never
silently trades a value the user did not choose.

The fees are deliberately **not** here: they are a fact of the account
(`CommissionRate`), not a choice, so they travel in `ExchangeTerms` with the
venue's filters. Live they come from the account; the backtest records them.

@par The definition's keys (all strings, as `BotDefinition.config` stores them)
`lower`, `upper`, `grid_count`, `spacing` (`ARITHMETIC` | `GEOMETRIC`),
`capital_quote`, `stop_loss` and `take_profit` — each `off`, `price:<p>` or
`percent:<n>` (n per cent beyond the range edge: below `lower` for a stop loss,
above `upper` for a take profit).

@par Direction and leverage (`EPIC-039B`)
`direction` (`LONG` | `SHORT` | `NEUTRAL`) and `leverage` (a whole number from 1). A definition
saved before they existed holds neither and is read as LONG at leverage 1 by
`exposure_of_a_saved_definition`, the one named migration; such a definition is written back
without them, so a Spot definition on disk keeps its bytes. A definition that names one must
name both, and one for a position venue must name both (`from_config_naming_exposure`).

@par Out of range (`EPIC-039H`, O6)
`on_range_exit` (`hold` | `close`): optional, `hold` when absent; `close` only on a position venue
(`exposure_refusal`). Written back only when it is `close`.

@par Trigger price (`EPIC-046A`)
`trigger_price` (a price inside the range): optional, absent (or `off`) when there is none. A LONG grid
activates when the price is at or below it, a SHORT grid when it is at or above it, like a limit
order on the entry (`grid_entry_gate.py`); a NEUTRAL grid has no better side and is refused.

@par A bot created with no parameters (`BOT-150`)
New bot asks only for the kind, venue and symbol; the parameters are set on
the draft afterwards. `unset_parameters` names the ones the user must still
type, in the user's words, and `unset_parameters_reason` asks for them, so the
verdict and the backtest ask rather than report a missing key.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)

_HUNDRED = Decimal(100)

#: The parameters that have no default, keyed by the definition's key, with
#: their words for the user. Every other one (grids, spacing, both exits) has a
#: default the editor starts at; `test_grid_panel.py` locks that the Grid panel
#: leaves blank exactly these.
PARAMETERS_WITHOUT_A_DEFAULT: Mapping[str, str] = {
    "lower": "lower price",
    "upper": "upper price",
    "capital_quote": "capital",
}


#: What a definition saved before `EPIC-039B` means: the Spot Grid, long, unlevered.
LEGACY_DIRECTION = TradeDirection.LONG
LEGACY_LEVERAGE = 1


class GridSpacing(str, Enum):
    """How the levels are spread across the range."""

    ARITHMETIC = "ARITHMETIC"
    GEOMETRIC = "GEOMETRIC"


class ExitKind(str, Enum):
    """How a stop loss or take profit is given."""

    OFF = "off"
    PRICE = "price"
    PERCENT = "percent"


class RangeExit(str, Enum):
    """What a position venue's bot does when the mark price leaves the range (`EPIC-039H`, O6).

    `HOLD` idles at the exposure it has (the default, and the only thing Spot does); `CLOSE`
    stops with the position closed at market, recorded as `GridReason.RANGE_EXIT`."""

    HOLD = "hold"
    CLOSE = "close"


class GridParamsError(ValueError):
    """The definition does not hold readable Grid parameters; the message names the key."""


@dataclass(frozen=True, slots=True)
class ExitLevel:
    """A stop loss or take profit: off, a price, or a percentage beyond the edge."""

    kind: ExitKind
    value: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.kind is not ExitKind.OFF and self.value <= 0:
            raise GridParamsError(f"a {self.kind.value} exit needs a positive value")

    def below(self, edge: Decimal) -> Decimal | None:
        """The price, for a stop loss under `edge`; `None` when off."""
        return self._resolve(edge, -1)

    def above(self, edge: Decimal) -> Decimal | None:
        """The price, for a take profit over `edge`; `None` when off."""
        return self._resolve(edge, 1)

    def encode(self) -> str:
        if self.kind is ExitKind.OFF:
            return ExitKind.OFF.value
        return f"{self.kind.value}:{self.value}"

    def _resolve(self, edge: Decimal, direction: int) -> Decimal | None:
        if self.kind is ExitKind.OFF:
            return None
        if self.kind is ExitKind.PRICE:
            return self.value
        return edge * (1 + direction * self.value / _HUNDRED)


@dataclass(frozen=True, slots=True)
class GridParams:
    """One Grid's range, ladder, capital and exits."""

    lower: Decimal
    upper: Decimal
    grid_count: int
    spacing: GridSpacing
    capital_quote: Decimal
    stop_loss: ExitLevel
    take_profit: ExitLevel
    direction: TradeDirection = LEGACY_DIRECTION
    leverage: int = LEGACY_LEVERAGE
    on_range_exit: RangeExit = RangeExit.HOLD
    trigger_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.lower <= 0:
            raise GridParamsError("lower must be positive")
        if self.upper <= self.lower:
            raise GridParamsError("upper must be above lower")
        if self.grid_count < 1:
            raise GridParamsError("grid_count must be at least 1")
        if self.capital_quote <= 0:
            raise GridParamsError("capital_quote must be positive")
        if self.stop_loss.kind is ExitKind.PERCENT and self.stop_loss.value >= _HUNDRED:
            raise GridParamsError("a stop_loss percent must be below 100")
        if self.leverage < 1:
            raise GridParamsError("leverage must be at least 1")
        self._check_trigger()

    def _check_trigger(self) -> None:
        trigger = self.trigger_price
        if trigger is None:
            return
        if self.direction is TradeDirection.NEUTRAL:
            raise GridParamsError(
                "a trigger price needs a LONG or SHORT grid: a NEUTRAL grid has no better side "
                "to wait for"
            )
        if not self.lower <= trigger <= self.upper:
            raise GridParamsError(
                f"the trigger price {trigger} must be inside the range "
                f"{self.lower}-{self.upper}"
            )

    @classmethod
    def from_config(cls, config: Mapping[str, str]) -> GridParams:
        """@raise GridParamsError A key is missing or unreadable."""
        direction, leverage = exposure_of_a_saved_definition(config)
        return cls(
            lower=_decimal(config, "lower"),
            upper=_decimal(config, "upper"),
            grid_count=_integer(config, "grid_count"),
            spacing=_spacing(config),
            capital_quote=_decimal(config, "capital_quote"),
            stop_loss=_exit(config, "stop_loss"),
            take_profit=_exit(config, "take_profit"),
            direction=direction,
            leverage=leverage,
            on_range_exit=_range_exit(config),
            trigger_price=_trigger_price(config),
        )

    @classmethod
    def from_config_naming_exposure(cls, config: Mapping[str, str]) -> GridParams:
        """A definition for a position venue: `direction` and `leverage` are both required.

        @raise GridParamsError A key, including either of those two, is missing or unreadable.
        """
        for key in (_DIRECTION_KEY, _LEVERAGE_KEY):
            _text(config, key)
        return cls.from_config(config)

    def to_config(self) -> dict[str, str]:
        config = {
            "lower": str(self.lower),
            "upper": str(self.upper),
            "grid_count": str(self.grid_count),
            "spacing": self.spacing.value,
            "capital_quote": str(self.capital_quote),
            "stop_loss": self.stop_loss.encode(),
            "take_profit": self.take_profit.encode(),
        }
        if (self.direction, self.leverage) != (LEGACY_DIRECTION, LEGACY_LEVERAGE):
            config[_DIRECTION_KEY] = self.direction.name
            config[_LEVERAGE_KEY] = str(self.leverage)
        if self.on_range_exit is not RangeExit.HOLD:
            config[_RANGE_EXIT_KEY] = self.on_range_exit.value
        if self.trigger_price is not None:
            config[_TRIGGER_PRICE_KEY] = str(self.trigger_price)
        return config

    @property
    def stop_loss_price(self) -> Decimal | None:
        """Where the stop loss sits: below the range for a grid that wins when price rises
        (Spot, LONG, NEUTRAL's long side), above it for a SHORT grid (`EPIC-039I`)."""
        if self.direction is TradeDirection.SHORT:
            return self.stop_loss.above(self.upper)
        return self.stop_loss.below(self.lower)

    @property
    def take_profit_price(self) -> Decimal | None:
        """Where the take profit sits: above the range, or below it for a SHORT grid."""
        if self.direction is TradeDirection.SHORT:
            return self.take_profit.below(self.lower)
        return self.take_profit.above(self.upper)


def exposure_of_a_saved_definition(
    config: Mapping[str, str],
) -> tuple[TradeDirection, int]:
    """The direction and leverage of `config`; LONG at 1 when it names neither.

    This is the migration of definitions saved before `EPIC-039B`: nothing else supplies a
    default for these keys. Naming one without the other is an error naming the missing one.

    @raise GridParamsError Only one of the two is named, or one is unreadable.
    """
    if _DIRECTION_KEY not in config and _LEVERAGE_KEY not in config:
        return LEGACY_DIRECTION, LEGACY_LEVERAGE
    return _direction(config), _leverage(config)


def unset_parameters(config: Mapping[str, str]) -> tuple[str, ...]:
    """The labels of `PARAMETERS_WITHOUT_A_DEFAULT` that `config` leaves out or blank."""
    return tuple(
        label
        for key, label in PARAMETERS_WITHOUT_A_DEFAULT.items()
        if not config.get(key, "").strip()
    )


def unset_parameters_reason(labels: tuple[str, ...]) -> str:
    """What the user is asked, for every consumer that judges a Grid's
    parameters (the planner's verdict, the backtest): "Set the lower price,
    upper price and capital."."""
    named = (
        labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} and {labels[-1]}"
    )
    return f"Set the {named}."


def _text(config: Mapping[str, str], key: str) -> str:
    try:
        return config[key].strip()
    except KeyError:
        raise GridParamsError(f"{key} is missing") from None


def _decimal(config: Mapping[str, str], key: str) -> Decimal:
    return _parse_decimal(_text(config, key), key)


def _parse_decimal(text: str, key: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise GridParamsError(f"{key} is not a number: {text!r}") from None
    if not value.is_finite():
        raise GridParamsError(f"{key} is not a finite number: {text!r}")
    return value


def _integer(config: Mapping[str, str], key: str) -> int:
    text = _text(config, key)
    if not (text.isascii() and text.isdigit()):
        raise GridParamsError(f"{key} is not a whole number: {text!r}")
    return int(text)


def _spacing(config: Mapping[str, str]) -> GridSpacing:
    text = _text(config, "spacing").upper()
    try:
        return GridSpacing(text)
    except ValueError:
        raise GridParamsError(
            f"spacing is not ARITHMETIC or GEOMETRIC: {text!r}"
        ) from None


_DIRECTION_KEY = "direction"
_LEVERAGE_KEY = "leverage"
_RANGE_EXIT_KEY = "on_range_exit"
_TRIGGER_PRICE_KEY = "trigger_price"


def _trigger_price(config: Mapping[str, str]) -> Decimal | None:
    """`None` when the key is absent, blank or `off` (how `bot edit` clears it, as for a stop loss):
    a definition saved before `EPIC-046A` has none, and `to_config` writes the key only when a
    trigger is set, so a saved definition keeps its bytes."""
    text = config.get(_TRIGGER_PRICE_KEY, "").strip()
    if not text or text.lower() == ExitKind.OFF.value:
        return None
    return _parse_decimal(text, _TRIGGER_PRICE_KEY)


def _range_exit(config: Mapping[str, str]) -> RangeExit:
    """`HOLD` when the key is absent: a definition saved before O6 held out of range, and a Spot
    definition keeps its bytes (`to_config` writes the key only for `CLOSE`)."""
    if _RANGE_EXIT_KEY not in config:
        return RangeExit.HOLD
    text = config[_RANGE_EXIT_KEY].strip().lower()
    try:
        return RangeExit(text)
    except ValueError:
        raise GridParamsError(f"on_range_exit is not hold or close: {text!r}") from None


def _direction(config: Mapping[str, str]) -> TradeDirection:
    text = _text(config, _DIRECTION_KEY).upper()
    try:
        return TradeDirection[text]
    except KeyError:
        raise GridParamsError(
            f"direction is not LONG, SHORT or NEUTRAL: {text!r}"
        ) from None


def _leverage(config: Mapping[str, str]) -> int:
    value = _integer(config, _LEVERAGE_KEY)
    if value < 1:
        raise GridParamsError(f"leverage must be at least 1: {value}")
    return value


def exit_level_of(config: Mapping[str, str], key: str) -> ExitLevel:
    """The stop loss or take profit `config` holds under `key`.

    @raise GridParamsError The key is missing or is not `off`, `price:<p>` or `percent:<n>`.
    """
    return _exit(config, key)


def _exit(config: Mapping[str, str], key: str) -> ExitLevel:
    text = _text(config, key).lower()
    if text == ExitKind.OFF.value:
        return ExitLevel(ExitKind.OFF)
    kind_text, separator, value_text = text.partition(":")
    try:
        kind = ExitKind(kind_text)
    except ValueError:
        raise GridParamsError(
            f"{key} is not off, price:<p> or percent:<n>: {text!r}"
        ) from None
    if not separator or kind is ExitKind.OFF:
        raise GridParamsError(f"{key} is not off, price:<p> or percent:<n>: {text!r}")
    return ExitLevel(kind, _parse_decimal(value_text, key))
