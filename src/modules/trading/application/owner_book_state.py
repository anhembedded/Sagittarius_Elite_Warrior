"""`BOT-207` — what the two sides of the owner books share: the books, the held events, the
departed symbols, and the one lock that guards them.

@details `OwnerBooks` (the lifecycle and the writes) and `OwnerBookReads` (what is asked of the
books) are built over one `OwnerBookState`, never over copies of it, so a read and a write take the
same lock and a read never sees a book half-way through a fill. Nothing here has behaviour: the two
sides are the only code that touches these fields.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_book import (
    IOwnerBook,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
        OwnerEventBuffer,
    )


class OwnerBookState:
    """@brief The budgeted owners' books on one venue, and the lock that guards them."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.by_tag: dict[str, IOwnerBook] = {}
        self.buffers: list[OwnerEventBuffer] = []
        # Symbols a position owner left (its stop closed it) whose flat report from the
        # exchange has not arrived yet (`BUG-233`).
        self.departed: set[str] = set()
