"""`EPIC-028J` — the lines a desk's summary panel shows, from one
`AccountSummary`.

@details Each market shows its own figures (`EPIC-028D`): a Futures desk
its available balance, wallet, unrealized PnL and margin balance; a Spot
desk its spendable quote, what open orders hold and the account's value.
A Multi-Assets Futures account counts every margin asset in USD, so its
figures say "USD", never "USDT" (`EPIC-028O`). An unknown Spot value is
said to be unknown, never shown as a partial sum.

Since `EPIC-033N` the panel shows them as a `Readout`: each figure a money
value written by the application's formatter, its unit in its title
("Available (USDT)") because the unit is the account's, not the number's.
Which rows a summary has is known only once it is read, so the readout
carries its rows with its values.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
    AssetMode,
    FuturesAccountSummary,
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, ColumnSpec

_UNPRICED = "unknown: a holding could not be priced"


def summary_readout(summary: AccountSummary | None) -> Readout | None:
    """@return The panel's rows and values; `None` when the account could not
    be read."""
    if isinstance(summary, FuturesAccountSummary):
        return _futures_readout(summary)
    if isinstance(summary, SpotAccountSummary):
        return _spot_readout(summary)
    if summary is None:
        return None
    return Readout(
        (_money("available", "Available", "USDT"),),
        {"available": summary.available_balance},
    )


def _money(key: str, title: str, unit: str) -> ColumnSpec:
    return ColumnSpec(key, f"{title} ({unit})", ColumnKind.MONEY)


def _futures_readout(summary: FuturesAccountSummary) -> Readout:
    multi = summary.asset_mode is AssetMode.MULTI_ASSETS
    unit = "USD" if multi else "USDT"
    specs = (
        _money("available", "Available", unit),
        _money("wallet", "Wallet balance", unit),
        _money("unrealized_pnl", "Unrealized PnL", unit),
        _money("margin_balance", "Margin balance", unit),
    )
    values = {
        "available": summary.available_balance,
        "wallet": summary.wallet_balance,
        "unrealized_pnl": summary.unrealized_pnl,
        "margin_balance": summary.margin_balance,
    }
    if not multi:
        return Readout(specs, values)
    margin = ColumnSpec("margin", "Margin", ColumnKind.TEXT)
    return Readout(
        (*specs, margin), {**values, "margin": "every margin asset (Multi-Assets)"}
    )


def _spot_readout(summary: SpotAccountSummary) -> Readout:
    quote = summary.quote_asset
    # An unknown account value is a sentence, not an amount: the row is text
    # then, so it says why rather than standing empty.
    equity = (
        _money("equity", "Account value", quote)
        if summary.equity is not None
        else ColumnSpec("equity", "Account value", ColumnKind.TEXT)
    )
    return Readout(
        (
            _money("available", "Available", quote),
            _money("in_orders", "In orders", quote),
            equity,
        ),
        {
            "available": summary.quote_free,
            "in_orders": summary.quote_locked,
            "equity": summary.equity if summary.equity is not None else _UNPRICED,
        },
    )
