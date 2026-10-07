"""`EPIC-034E` — what an API key may do, as the exchange says it
(`GET /sapi/v1/account/apiRestrictions`).

@details The permissions that decide whether the app may hold the key. A key
that can withdraw is refused (D5). A key that can do more than read (trade Spot,
Margin or Futures, or transfer between accounts) is accepted read-only, with
advice to create a key that cannot: the app places nothing, but the screen must
not call such a key "read only".

The three flags the decision rests on are exact: the parser raises when the
exchange leaves one out, never a guessed `False`. The other flags are `None`
when the answer did not carry them, which is not "off": such a key is not
called read only either.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyPermissions:
    can_read: bool
    can_trade_spot: bool
    can_withdraw: bool
    can_trade_margin: bool | None = None
    can_trade_futures: bool | None = None
    #: Internal or universal transfer between the owner's accounts.
    can_transfer: bool | None = None

    @property
    def is_read_only(self) -> bool:
        """Certainly nothing beyond reading: every flag is known and off."""
        return (
            self.can_read
            and not self.can_withdraw
            and self.can_trade_spot is False
            and self.can_trade_margin is False
            and self.can_trade_futures is False
            and self.can_transfer is False
        )

    @property
    def beyond_reading(self) -> tuple[str, ...]:
        """What the key can do besides read, in words; empty when it can do
        nothing else or the exchange did not say."""
        granted = (
            (self.can_trade_spot, "trade Spot"),
            (self.can_trade_margin, "trade Margin"),
            (self.can_trade_futures, "trade Futures"),
            (self.can_transfer, "transfer between accounts"),
        )
        return tuple(words for flag, words in granted if flag)
