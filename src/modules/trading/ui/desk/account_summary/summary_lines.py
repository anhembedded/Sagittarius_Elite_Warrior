"""`EPIC-028J` — the lines a desk's summary panel shows, from one
`AccountSummary`.

@details Each market shows its own figures (`EPIC-028D`): a Futures desk
its available balance, wallet, unrealized PnL and margin balance; a Spot
desk its spendable quote, what open orders hold and the account's value.
A Multi-Assets Futures account counts every margin asset in USD, so its
figures say "USD", never "USDT" (`EPIC-028O`). An unknown Spot value is
said to be unknown, never shown as a partial sum.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
    AssetMode,
    FuturesAccountSummary,
    SpotAccountSummary,
)

_UNPRICED = "unknown: a holding could not be priced"


@dataclass(frozen=True)
class SummaryLine:
    label: str
    value_text: str


def summary_lines_for(summary: AccountSummary | None) -> tuple[SummaryLine, ...]:
    """@return The panel's lines; empty when the account could not be read."""
    if isinstance(summary, FuturesAccountSummary):
        return _futures_lines(summary)
    if isinstance(summary, SpotAccountSummary):
        return _spot_lines(summary)
    if summary is None:
        return ()
    return (SummaryLine("Available", _amount(summary.available_balance, "USDT")),)


def _futures_lines(summary: FuturesAccountSummary) -> tuple[SummaryLine, ...]:
    unit = "USD" if summary.asset_mode is AssetMode.MULTI_ASSETS else "USDT"
    lines = (
        SummaryLine("Available", _amount(summary.available_balance, unit)),
        SummaryLine("Wallet balance", _amount(summary.wallet_balance, unit)),
        SummaryLine("Unrealized PnL", f"{summary.unrealized_pnl:+,.2f} {unit}"),
        SummaryLine("Margin balance", _amount(summary.margin_balance, unit)),
    )
    if summary.asset_mode is AssetMode.MULTI_ASSETS:
        return (*lines, SummaryLine("Margin", "every margin asset (Multi-Assets)"))
    return lines


def _spot_lines(summary: SpotAccountSummary) -> tuple[SummaryLine, ...]:
    quote = summary.quote_asset
    equity = _amount(summary.equity, quote) if summary.equity is not None else _UNPRICED
    return (
        SummaryLine("Available", _amount(summary.quote_free, quote)),
        SummaryLine("In orders", _amount(summary.quote_locked, quote)),
        SummaryLine("Account value", equity),
    )


def _amount(value: Decimal, unit: str) -> str:
    return f"{value:,.2f} {unit}"
