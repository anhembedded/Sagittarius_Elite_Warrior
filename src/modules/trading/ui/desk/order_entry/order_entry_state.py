"""`BOT-152` — the order panel's state, held once and shared by the three
objects that touch it.

@details `OrderEntryViewModel` reads it, `OrderEntryUserIntents` changes it
for the user and `OrderEntryPresenterWriter` changes it for the presenter. It
is plain data with no signal of its own: whoever changes it emits `changed`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
    SideInput,
)


def blank_entries() -> dict[EntrySide, SideInput]:
    """@return Nothing typed on either side."""
    return {side: SideInput() for side in EntrySide}


@dataclass
class OrderEntryState:
    """@brief What the panel holds: the chosen order type, what each side
    typed, what the exchange said about the symbol and whether an order is in
    flight."""

    profile: DeskProfile
    order_type: OrderType
    symbol: str = ""
    context: OrderEntryContext | None = None
    last_price: Decimal | None = None
    entries: dict[EntrySide, SideInput] = field(default_factory=blank_entries)
    busy: bool = False
    message: str = ""
    message_is_error: bool = False
    #: True from `begin_symbol` until the symbol's terms are first read.
    loading: bool = False

    def store(self, side: EntrySide, updated: SideInput) -> bool:
        """@return Whether `updated` differs from what the side held, so the
        caller knows to emit `changed`."""
        if updated == self.entries[side]:
            return False
        self.entries[side] = updated
        return True
