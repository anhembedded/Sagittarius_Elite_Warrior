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
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

_HUNDRED = Decimal(100)


class GridSpacing(str, Enum):
    """How the levels are spread across the range."""

    ARITHMETIC = "ARITHMETIC"
    GEOMETRIC = "GEOMETRIC"


class ExitKind(str, Enum):
    """How a stop loss or take profit is given."""

    OFF = "off"
    PRICE = "price"
    PERCENT = "percent"


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

    def __post_init__(self) -> None:
        if self.lower <= 0:
            raise GridParamsError("lower must be positive")
        if self.upper <= self.lower:
            raise GridParamsError("upper must be above lower")
        if self.grid_count < 1:
            raise GridParamsError("grid_count must be at least 1")
        if self.capital_quote <= 0:
            raise GridParamsError("capital_quote must be positive")

    @classmethod
    def from_config(cls, config: Mapping[str, str]) -> GridParams:
        """@raise GridParamsError A key is missing or unreadable."""
        return cls(
            lower=_decimal(config, "lower"),
            upper=_decimal(config, "upper"),
            grid_count=_integer(config, "grid_count"),
            spacing=_spacing(config),
            capital_quote=_decimal(config, "capital_quote"),
            stop_loss=_exit(config, "stop_loss"),
            take_profit=_exit(config, "take_profit"),
        )

    def to_config(self) -> dict[str, str]:
        return {
            "lower": str(self.lower),
            "upper": str(self.upper),
            "grid_count": str(self.grid_count),
            "spacing": self.spacing.value,
            "capital_quote": str(self.capital_quote),
            "stop_loss": self.stop_loss.encode(),
            "take_profit": self.take_profit.encode(),
        }

    @property
    def stop_loss_price(self) -> Decimal | None:
        return self.stop_loss.below(self.lower)

    @property
    def take_profit_price(self) -> Decimal | None:
        return self.take_profit.above(self.upper)


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
    if not text.isdigit():
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
