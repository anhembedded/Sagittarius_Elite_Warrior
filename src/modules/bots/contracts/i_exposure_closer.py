"""`EPIC-039H` — how a Grid's stop closes what the bot holds, per venue profile.

@details The stop is the same sequence on every venue — register, cancel the tagged orders,
close the exposure when asked, confirm nothing of the bot's still rests — and only the close
differs. Spot sells the base the bot bought, in slices under the per-order cap; a position
venue (`closer_futures.py`) sends reduce-only market orders for the position and confirms it flat. The sequence
(`GridStopSequence`) holds one closer and never asks what market it is on.

A closer answers `None` when the exposure is closed (or was dust), and otherwise how the stop
ended, so the retry machinery (`GridStopRetry`) is shared too. It never leaves the bot half
closed silently: a slice that failed halts the bot naming what stayed unsold.

Plausible extensions, each a local change: a second venue profile (Coin-M, delivery) is one
more closer and one registration in `GridExposures`; a protective-stop-aware close (`EPIC-039L`)
is a decorator of the position closer that cancels the exchange-side stop after the close.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)


class IExposureCloser(ABC):
    @abstractmethod
    def closes_on_halt(self) -> bool:
        """Whether a halt closes what the bot holds after taking its ladder off. Spot leaves
        the base it bought; a position venue never leaves a leveraged position bare unless an
        exchange-side stop stands (decision O8, `EPIC-039L`)."""

    @abstractmethod
    def close(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        """Close what `registration` (just derived, after the tagged orders were cancelled)
        says the bot holds, with `price` as the exit's reference.

        @return `None` when nothing of the exposure remains; otherwise how the stop ended."""
