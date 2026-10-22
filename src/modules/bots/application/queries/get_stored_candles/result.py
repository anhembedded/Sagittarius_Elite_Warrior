"""`BOT-233` — what the stored candles of a period are, and how much of the period they cover."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData


@dataclass(frozen=True, slots=True)
class StoredCandles:
    """The candles stored for a period, oldest first, against the closed candles it holds.

    `candles` is empty when `too_many`: a period that long is not read at all."""

    candles: tuple[MarketData, ...]
    #: The candles that open in the period and close by its end.
    expected: int
    #: Of those, how many are stored.
    stored: int
    #: The most candles one backtest draws (`MAX_CANDLES`), told in the refusal's words.
    limit: int
    #: The period holds more candles than one backtest draws (`MAX_CANDLES`).
    too_many: bool = False

    @property
    def missing(self) -> int:
        """Candles of the period not stored: not there at all, or gaps."""
        return max(self.expected - self.stored, 0)

    @property
    def needs_sync(self) -> bool:
        """Whether a sync would add candles to the period: some are not stored, and it is a period
        that is read at all."""
        return not self.too_many and self.missing > 0
