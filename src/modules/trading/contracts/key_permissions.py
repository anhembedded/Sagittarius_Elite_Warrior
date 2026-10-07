"""`EPIC-034E` — what an API key may do, as the exchange says it
(`GET /sapi/v1/account/apiRestrictions`).

@details Only the permissions that decide whether the app may hold the key.
A key that can withdraw is refused (D5); one that can trade is accepted
read-only, with advice to create a key that cannot. `None` of these is ever a
guessed `False`: the parser raises when the exchange's answer lacks one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyPermissions:
    can_read: bool
    can_trade_spot: bool
    can_withdraw: bool

    @property
    def is_read_only(self) -> bool:
        return self.can_read and not self.can_trade_spot and not self.can_withdraw
