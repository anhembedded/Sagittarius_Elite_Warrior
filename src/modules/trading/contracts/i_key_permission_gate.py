"""`EPIC-034` D5 — the step that refuses a key which can move money out.

@details A mainnet venue's key is checked before any account data is read: one
that can withdraw is refused, whatever else it can do. It blocks no order a
usable key could place — it is the owner's own earlier decision (D5), kept when
mainnet became tradable (D11). A testnet venue has no such step (a testnet has
no `apiRestrictions` endpoint). It is a step of the one snapshot assembler
(`ComposedVenueAccountReader`), not a second reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)


class IKeyPermissionGate(ABC):
    @abstractmethod
    def check(self) -> ConnectFailure | None:
        """Why the key may not be used (no key `NOT_CONFIGURED`, a key that
        can withdraw `WITHDRAWAL_ENABLED`, the exchange not answering, an
        answer that cannot be read), or `None` when it may. Never raises."""
