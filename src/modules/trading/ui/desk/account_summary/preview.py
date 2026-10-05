"""Standalone preview of a desk's account summary (`ui-presentation-rule.md`
§5), without an exchange: a Futures account in Multi-Assets mode, so the
figures are in USD, marked stale with the reason a failed read gives."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.account_summary_panel import (
    AccountSummaryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.summary_lines import (
    summary_readout,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def build_preview() -> QWidget:
    panel = AccountSummaryPanel()
    panel.show_readout(
        summary_readout(
            FuturesAccountSummary(
                venue=TradingVenue.FUTURES_TESTNET,
                available_balance=Decimal("4210.55"),
                equity=Decimal("5032.10"),
                wallet_balance=Decimal("5039.63"),
                margin_balance=Decimal("5032.10"),
                unrealized_pnl=Decimal("-7.53"),
                position_mode=PositionMode.ONE_WAY,
                asset_mode=AssetMode.MULTI_ASSETS,
            )
        )
    )
    panel.mark_stale("the venue did not answer for 30 seconds")
    panel.setWindowTitle("Account summary — Futures")
    return panel
