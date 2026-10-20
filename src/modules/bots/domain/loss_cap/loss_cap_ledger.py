"""`EPIC-026L` — what the host's bots have made or lost since 00:00 UTC (decision N3).

A bot's run account (`RunEarnings.total_pnl`) is the whole run's realised plus unrealised result,
not the day's. The day's part is the account now less the account when the day (or the bot, or
the run) was first seen, plus whatever earlier runs of the bot booked today. The ledger keeps
exactly that per bot; the sum over bots is the figure the cap compares with the owner's amount.

@par One bot's day
  · `baseline` — the run account when this ledger first saw the run, or 0 for a run that began
    today (its whole account is today's);
  · `last` — the run account at the latest sample;
  · `banked` — the day's result of the bot's earlier runs, closed when a new run began.
  The bot's day result is `banked + last - baseline`.

A bot with no readable account at a sample keeps its last figure; the caller decides whether that
is a reason to trip (`loss_cap_policy.py`). A bot that is deleted keeps its figure, because what it
lost today was lost.

Pure `Decimal` arithmetic over frozen values: the unit tests drive the arithmetic and the day
boundary without a clock, a file or a bot.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import MappingProxyType

_ZERO = Decimal(0)


def day_start_of(day: date) -> datetime:
    """00:00 UTC of `day`."""
    return datetime.combine(day, time(0, 0), tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BotObservation:
    """What one sample read of one bot. `pnl` is `None` when the bot's account cannot be read
    in the cap's quote asset (no price yet, no run account, another quote asset)."""

    bot_id: str
    run_started_at: datetime | None
    pnl: Decimal | None
    at_rest: bool

    @property
    def is_unjudged(self) -> bool:
        """A bot that may hold risk whose result is not known."""
        return not self.at_rest and self.pnl is None


@dataclass(frozen=True, slots=True)
class BotDayFigure:
    """One bot's part of the day; see the module docstring."""

    run_started_at: datetime | None
    baseline: Decimal
    last: Decimal
    banked: Decimal = _ZERO

    @property
    def day_pnl(self) -> Decimal:
        return self.banked + self.last - self.baseline

    def seen_again(
        self, observed: BotObservation, pnl: Decimal, day_start: datetime
    ) -> BotDayFigure:
        """The figure after another sample of the same bot."""
        if observed.run_started_at == self.run_started_at:
            return replace(self, last=pnl)
        # A new run: its account starts again from nothing, and the old run's day is banked.
        return BotDayFigure(
            observed.run_started_at,
            _baseline_of(observed.run_started_at, pnl, day_start),
            pnl,
            self.day_pnl,
        )


def _baseline_of(
    run_started_at: datetime | None, pnl: Decimal, day_start: datetime
) -> Decimal:
    began_today = run_started_at is not None and run_started_at >= day_start
    return _ZERO if began_today else pnl


@dataclass(frozen=True, slots=True)
class LossCapLedger:
    """The day's figures by bot id, for one UTC day."""

    day: date
    figures: Mapping[str, BotDayFigure]

    def __post_init__(self) -> None:
        object.__setattr__(self, "figures", MappingProxyType(dict(self.figures)))

    @classmethod
    def empty(cls, day: date) -> LossCapLedger:
        return cls(day, {})

    @property
    def day_pnl(self) -> Decimal:
        """The sum of every bot's day result: negative is a loss."""
        return sum((figure.day_pnl for figure in self.figures.values()), _ZERO)

    def observe(self, observations: Iterable[BotObservation]) -> LossCapLedger:
        """The ledger after one sample. An observation with no `pnl` changes nothing."""
        start = day_start_of(self.day)
        figures = dict(self.figures)
        for observed in observations:
            if observed.pnl is None:
                continue
            known = figures.get(observed.bot_id)
            figures[observed.bot_id] = (
                known.seen_again(observed, observed.pnl, start)
                if known is not None
                else BotDayFigure(
                    observed.run_started_at,
                    _baseline_of(observed.run_started_at, observed.pnl, start),
                    observed.pnl,
                )
            )
        return LossCapLedger(self.day, figures)
