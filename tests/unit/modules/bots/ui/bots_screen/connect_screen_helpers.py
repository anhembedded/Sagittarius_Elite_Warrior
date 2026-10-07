"""What the Connect step's screen tests share: selecting, what the chart place
shows, Start's rule, and the two answers a venue can give."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard

from .bots_screen_fixtures import NOW, BotsScreen

_SPOT = AccountSource.SPOT_TESTNET


def select(screen: BotsScreen, bot_id: str) -> None:
    screen.view.model.select_requested.emit(bot_id)


def chart_shown(screen: BotsScreen) -> bool:
    return any(
        card.parent() is not None
        for card in screen.view.chart_area.findChildren(ChartCard)
    )


def locked_note(screen: BotsScreen) -> str:
    notes = [
        label.text()
        for label in screen.view.chart_area.findChildren(QLabel)
        if label.objectName() == "lblBotsChartLocked"
    ]
    return notes[0] if notes else ""


def start_rule(screen: BotsScreen) -> tuple[bool, str]:
    rule = screen.view.model.availability[BotAction.START]
    return rule.enabled, rule.reason


#: More than any capital the screen tests plan with, so the balance
#: constraint (`EPIC-034F`) passes unless a test is about it.
FUNDED = Decimal(50_000)


def fresh_snapshot() -> VenueAccountSnapshot:
    return replace(a_venue_account_snapshot(), read_at=NOW, available=FUNDED)


def failure(kind: ConnectionFailureKind, detail: str = "the account") -> ConnectFailure:
    return ConnectFailure(_SPOT, kind, detail)
