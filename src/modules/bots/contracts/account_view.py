"""`EPIC-034F` — the Connect step's snapshot, narrowed to what a kind's
constraints read.

The snapshot is trading's value (`VenueAccountSnapshot`); a kind's domain names
no other module, so it reads this `AccountView` instead. One mapping serves the
screen's judgement and the readiness query (`EPIC-034H`), so the balance a plan
is held to on screen is the balance Start is held to. A published value mapping, not an
assessment, so it lives with the module's contracts (`EPIC-048B`): the screen maps the account
its Connect step read without reaching an application internal (`architecture-rule.md` §3.1).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    MarginView,
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


def margin_view_of(snapshot: VenueAccountSnapshot) -> MarginView:
    """The same snapshot, in a Futures venue's words: what a new order can reserve as
    margin (`EPIC-039E`). Beside `account_view_of`, which Spot keeps as it was."""
    return MarginView(
        available_margin=snapshot.available,
        quote_asset=snapshot.quote_asset,
        can_trade=snapshot.can_trade,
        venue_title=snapshot.source.venue_title,
    )
