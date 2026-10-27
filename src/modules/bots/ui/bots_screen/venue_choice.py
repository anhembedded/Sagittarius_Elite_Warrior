"""`BOT-171` — the venue pickers' combo box rows.

@details New bot and the Plan's Venue field offer the same list, which `GetVenueChoicesQuery`
answers (`EPIC-048B`): every venue a bot kind runs on, each with its connection state, a closed
one greyed out with its reason (`BUG-208`). The values live in `bots/contracts/venue_choice.py`
and are re-exported here for the views that list them. Whether a key *works* is the Connect
step's read, made once a bot is on the venue, and its failure is told once, in the message bar
(`BUG-181`).
"""

from __future__ import annotations

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QComboBox
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_choice import (
    KEY_SAVED,
    NO_KEY,
    NOT_ENABLED,
    VenueChoice,
)

__all__ = ["KEY_SAVED", "NOT_ENABLED", "NO_KEY", "VenueChoice", "add_venue_choice"]


def add_venue_choice(combo: QComboBox, choice: VenueChoice) -> None:
    """List `choice` in `combo`; a closed venue is shown greyed out, unselectable, with
    its reason as the tooltip (`BUG-208`). Both venue pickers list through here."""
    combo.addItem(choice.option_text, choice.venue)
    model = combo.model()
    if choice.closed_reason is None or not isinstance(model, QStandardItemModel):
        return
    item = model.item(combo.count() - 1)
    if item is not None:
        item.setEnabled(False)
        item.setToolTip(choice.closed_reason)
