"""`EPIC-034F` — the Connect step's snapshot, narrowed to what a kind's
constraints read.

The snapshot is trading's value (`VenueAccountSnapshot`); a kind's domain names
no other module, so it reads this `AccountView` instead. One mapping serves the
screen's judgement and the readiness query (`EPIC-034H`), so the balance a plan
is held to on screen is the balance Start is held to.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)


def account_view_of(snapshot: VenueAccountSnapshot) -> AccountView:
    return AccountView(
        available_quote=snapshot.available,
        quote_asset=snapshot.quote_asset,
        can_trade=snapshot.can_trade,
        venue_title=snapshot.source.venue_title,
    )
