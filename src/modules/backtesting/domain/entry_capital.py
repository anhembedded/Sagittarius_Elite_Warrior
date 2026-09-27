"""`EPIC-027C` — what one entry commits, or why the exchange refused it."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.entry_rejection_reason import (
    EntryRejectionReason,
)


@dataclass(frozen=True)
class EntryCapital:
    """
    @brief `FillPricing.entry_capital()`'s answer: the margin, quantity and fee
    of an entry that can fill, or the reason it cannot.
    @details Three zeros used to mean every refusal alike. An exchange filter
    refusal is a result fact the run counts (`BacktestResult.rejected_entries`),
    while an unfundable entry is not, so the two are told apart here.
    """

    margin: float
    quantity: float
    entry_fee: float
    #: Set when an exchange filter refused an entry that was otherwise fundable.
    rejection: EntryRejectionReason | None = None

    @property
    def is_fillable(self) -> bool:
        return self.rejection is None and self.quantity > 0 and self.margin > 0


#: An entry the account cannot pay for at all — not an exchange rule.
UNFUNDABLE = EntryCapital(margin=0.0, quantity=0.0, entry_fee=0.0)
