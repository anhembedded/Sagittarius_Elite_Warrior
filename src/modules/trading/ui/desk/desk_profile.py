"""`EPIC-028` ADR D5 — what makes one trading desk differ from the other,
as data.

@details Both desks are built from the same kit; a `DeskProfile` says which
venue a desk trades, which order types its panel offers, how the panel lays
out its two sides and how each side's figures are computed. A widget reads
the profile; no widget asks whether it is on Spot.

`EPIC-028I` adds the Futures desk: Buy/Long and Sell/Short sides sized by
the Futures estimates, Stop-limit among its order types (ADR O3), TP/SL
available, Positions in its account tabs, and the Futures controls
(reduce-only, margin mode, leverage).

Plausible extensions, each one entry in `_PROFILE_BUILDERS` plus whatever new
data it names:
- a one-form layout (Binance's Futures panel: one price and amount, two
  buttons): one `SideLayout` member and its widget;
- a mainnet venue: a profile for the new `TradingVenue` member, the same
  layout.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_rules import (
    futures_side_figures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
    SideFigures,
    SideInput,
    spot_side_figures,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The one quote asset this app trades in, on both venues: Spot pairs are
#: quoted in it and USD-M Futures margin is held in it. The same literal the
#: holdings and manual-order code already carry (`EPIC-027N`).
_QUOTE_ASSET = "USDT"

type SideFiguresRule = Callable[
    [EntrySide, OrderType, SideInput, OrderEntryContext, Decimal | None],
    SideFigures,
]


class HeldTab(str, Enum):
    """What the desk's account tabs list as held (`EPIC-028J`)."""

    #: Futures: open positions, each closable at market.
    POSITIONS = "positions"
    #: Spot: the assets the account holds.
    ASSETS = "assets"


class SideLayout(str, Enum):
    """How the order panel lays out its two sides."""

    #: A Buy form and a Sell form side by side, each with its own price and
    #: amount (Binance's Spot layout).
    TWO_COLUMNS = "two_columns"


@dataclass(frozen=True)
class DeskProfile:
    """One desk's venue and the choices that follow from it."""

    venue: TradingVenue
    market_type: MarketType
    title: str
    quote_asset: str
    order_types: tuple[OrderType, ...]
    side_layout: SideLayout
    buy_label: str
    sell_label: str
    figures: SideFiguresRule
    #: Why the panel's TP/SL toggle is off on this desk; `None` once the
    #: desk can place protective orders (the Futures desk, `EPIC-028I`).
    #: ADR O2: the toggle stays visible, so the missing feature is named
    #: rather than hidden.
    tp_sl_unavailable_reason: str | None
    #: Positions on Futures, Assets on Spot (`EPIC-028J`).
    held_tab: HeldTab
    #: `EPIC-028I` — whether the panel shows reduce-only and the margin-mode
    #: and leverage chips; only a venue with leverage has them.
    futures_controls: bool = False

    def side_label(self, side: EntrySide) -> str:
        return self.buy_label if side is EntrySide.BUY else self.sell_label


class DeskNotBuiltError(LookupError):
    """No desk exists for this venue yet."""


def _spot_profile(venue: TradingVenue) -> DeskProfile:
    return DeskProfile(
        venue=venue,
        market_type=MarketType.SPOT,
        title="Spot",
        quote_asset=_QUOTE_ASSET,
        order_types=(OrderType.LIMIT, OrderType.MARKET, OrderType.STOP_LIMIT),
        side_layout=SideLayout.TWO_COLUMNS,
        buy_label="Buy",
        sell_label="Sell",
        figures=spot_side_figures,
        tp_sl_unavailable_reason=(
            "TP/SL on Spot needs OCO orders, which arrive with the exchange-side "
            "protective orders (EPIC-026K)."
        ),
        held_tab=HeldTab.ASSETS,
    )


def _futures_profile(venue: TradingVenue) -> DeskProfile:
    return DeskProfile(
        venue=venue,
        market_type=MarketType.FUTURES_USD_M,
        title="Futures",
        quote_asset=_QUOTE_ASSET,
        order_types=(OrderType.LIMIT, OrderType.MARKET, OrderType.STOP_LIMIT),
        side_layout=SideLayout.TWO_COLUMNS,
        buy_label="Buy/Long",
        sell_label="Sell/Short",
        figures=futures_side_figures,
        tp_sl_unavailable_reason=None,
        held_tab=HeldTab.POSITIONS,
        futures_controls=True,
    )


_PROFILE_BUILDERS: dict[MarketType, Callable[[TradingVenue], DeskProfile]] = {
    MarketType.SPOT: _spot_profile,
    MarketType.FUTURES_USD_M: _futures_profile,
}


def desk_profile_for(venue: TradingVenue) -> DeskProfile:
    """@return The profile of the desk that trades `venue`.
    @raise DeskNotBuiltError `venue` trades no market (`DISABLED`)."""
    market = venue.market_type
    builder = _PROFILE_BUILDERS.get(market) if market is not None else None
    if builder is None:
        raise DeskNotBuiltError(f"no desk is built for {venue.value}")
    return builder(venue)
