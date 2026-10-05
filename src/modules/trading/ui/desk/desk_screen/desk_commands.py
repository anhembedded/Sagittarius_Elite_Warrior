"""A desk's commands: Enable live trading and Emergency stop (`EPIC-033D`),
and New order… (`EPIC-033R`).

Each is one `QAction` in the Trade menu and on its desk's toolbar, scoped to
that desk's mode, so the Futures desk's F8 never stops Spot. The ids carry
the venue, which both the module (when it contributes) and the desk presenter
(when it binds) know.

Emergency stop asks first: it cancels and closes, and that cannot be undone
(`ui-presentation-rule.md` §10). Enable live trading does not ask today. The
catalogue (HLD §11.2.3) wants a confirmation on enable only, and the Engine's
action confirms on every trigger, which would also ask before turning trading
off. That is recorded in `EPIC-033D`'s notes.

New order… (F9, as in MetaTrader) moves the keyboard focus to the order
entry's first field and places nothing; the order is placed by the entry's own
button, with its confirmation, so the command itself asks nothing. It ends
with "…" because the order needs input before it is sent.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandConfirmation,
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

TRADE_MENU = ("T&rade",)
_CONTRIBUTOR = "trading"

#: What Emergency stop does after turning trading off, per market
#: (`EmergencyStopCommandHandler`, step 3).
_WHAT_IT_CLOSES = {
    MarketType.FUTURES_USD_M: "every position is closed at market",
    MarketType.SPOT: "what was bought since trading was enabled is sold at market",
}


def enable_trading_id(venue: TradingVenue) -> str:
    return f"trading.{venue.value}.enable_trading"


def emergency_stop_id(venue: TradingVenue) -> str:
    return f"trading.{venue.value}.emergency_stop"


def new_order_id(venue: TradingVenue) -> str:
    return f"trading.{venue.value}.new_order"


def desk_commands(route: str, venue: TradingVenue) -> tuple[CommandContribution, ...]:
    """The commands of the desk at `route`, which trades `venue`."""
    profile = desk_profile_for(venue)
    return (
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=enable_trading_id(venue),
            text="&Enable live trading",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=emergency_stop_id(venue),
            text="Emergency &stop",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            shortcut="F8",
            confirm=CommandConfirmation(
                title="Emergency stop",
                consequence=(
                    f"Live trading on {profile.title} Testnet turns off, every "
                    f"open order is cancelled, and "
                    f"{_WHAT_IT_CLOSES[profile.market_type]}."
                ),
                accept_text="Stop everything",
            ),
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=new_order_id(venue),
            text="&New order…",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            shortcut="F9",
            needs_input=True,
        ),
    )
