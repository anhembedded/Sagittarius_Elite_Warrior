"""`BOT-125` — Vietnamese labels for the two exchange-environment enums.

@details One table per enum, and a guard test that every member has a
label. Deriving the text from the enum value (`"futures_testnet"` ->
`"Futures Testnet"`) would look like it works and then quietly produce
"Disabled" for the one member whose meaning a user most needs stated
plainly — `TradingVenue.DISABLED` does not mean "off" in a vague sense, it
means no order can leave this app at all, which is worth a whole sentence
rather than one word.

Labels carry the value in parentheses on purpose: the same strings appear
in `app_config.json`, in `EPIC-021`'s docs and in log lines, and a user
following any of those needs to recognise what they picked here.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

MARKET_DATA_VENUE_LABELS = EnumLabels(
    MarketDataVenue,
    {
        MarketDataVenue.MAINNET_PUBLIC: "Mainnet — real, public prices (mainnet_public)",
        MarketDataVenue.FUTURES_TESTNET: "Futures Testnet — testnet prices (futures_testnet)",
    },
)

TRADING_VENUE_LABELS = EnumLabels(
    TradingVenue,
    {
        TradingVenue.DISABLED: "OFF — no orders are sent anywhere (disabled)",
        TradingVenue.FUTURES_TESTNET: (
            "ON — Futures Testnet, simulated funds (futures_testnet)"
        ),
    },
)


def market_data_venue_label(venue: MarketDataVenue) -> str:
    return MARKET_DATA_VENUE_LABELS[venue]


def trading_venue_label(venue: TradingVenue) -> str:
    return TRADING_VENUE_LABELS[venue]
