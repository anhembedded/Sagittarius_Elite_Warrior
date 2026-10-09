"""`EPIC-034` D3, D11 — the bots screen asks the question that names real money
before a mainnet venue's first Start, Resume or Arm, and a "no" sends nothing.

What is asked and when is the real wiring (`command_for`, `dialogs_for`); whether
a venue needs asking at all is the consent's (`test_real_money_consent.py`), here a
recording fake.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot.command import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_commands import (
    command_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
    dialogs_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_real_money_consent import (
    FakeRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_MAINNET = TradingVenue.SPOT_MAINNET


@pytest.fixture(autouse=True)
def _application(qapp: object) -> None:
    """A widget needs the application to exist."""


def _bot(venue: TradingVenue = _MAINNET) -> BotSnapshot:
    return BotSnapshot(
        "a00001",
        "g",
        "grid",
        venue,
        "BTCUSDT",
        BotLifecycleState.DRAFT,
        datetime(2026, 10, 4, tzinfo=UTC),
        None,
    )


def _dialogs(consent: FakeRealMoneyConsent) -> BotsDialogs:
    return dialogs_for(QWidget(), Mock(), consent)


@pytest.mark.parametrize(
    "action", [BotAction.START, BotAction.RESUME, BotAction.CONFIRM_RESUME]
)
def test_what_puts_orders_on_a_mainnet_venue_asks_first(action: BotAction) -> None:
    consent = FakeRealMoneyConsent(agrees=True)

    command = command_for(action, _bot(), _dialogs(consent))

    assert command is not None
    assert consent.asked == [(_MAINNET, "start this bot")]


@pytest.mark.parametrize(
    "action", [BotAction.START, BotAction.RESUME, BotAction.CONFIRM_RESUME]
)
def test_declining_real_money_sends_nothing(action: BotAction) -> None:
    consent = FakeRealMoneyConsent(agrees=False)

    assert command_for(action, _bot(), _dialogs(consent)) is None


def test_start_sends_the_start_command_once_agreed() -> None:
    command = command_for(
        BotAction.START, _bot(), _dialogs(FakeRealMoneyConsent(agrees=True))
    )

    assert command == StartBotCommand("a00001", real_money_confirmed=True)


@pytest.mark.parametrize("action", [BotAction.PAUSE, BotAction.SAVE])
def test_what_places_no_order_asks_nothing(action: BotAction) -> None:
    consent = FakeRealMoneyConsent(agrees=False)

    command = command_for(action, _bot(), _dialogs(consent))

    assert command is not None  # not refused: nothing was asked
    assert consent.asked == []


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET]
)
def test_a_testnet_bot_starts_without_the_question(venue: TradingVenue) -> None:
    consent = FakeRealMoneyConsent(agrees=False)

    command = command_for(BotAction.START, _bot(venue), _dialogs(consent))

    assert command == StartBotCommand("a00001", real_money_confirmed=True)
    assert consent.asked == []


def test_arming_a_strategy_on_a_mainnet_venue_asks_first_and_a_no_arms_nothing() -> (
    None
):
    consent = FakeRealMoneyConsent(agrees=False)

    armed = _dialogs(consent).ask_arm_strategy(_MAINNET, Mock())

    assert armed is False  # the dialog was never opened: the question stopped it
    assert consent.asked == [(_MAINNET, "arm a strategy")]


def test_save_and_start_with_edits_asks_first_and_a_no_sends_nothing() -> None:
    """`EPIC-034H` D8 made Start "Save and start": the edits travel with it. On a
    mainnet venue the question comes before they do, so a "no" saves nothing
    either."""
    consent = FakeRealMoneyConsent(agrees=False)

    command = command_for(
        BotAction.START, _bot(), _dialogs(consent), {"capital_quote": "1500"}
    )

    assert command is None
    assert consent.asked == [(_MAINNET, "start this bot")]


def test_save_and_start_with_edits_carries_them_once_real_money_is_agreed() -> None:
    consent = FakeRealMoneyConsent(agrees=True)

    command = command_for(
        BotAction.START, _bot(), _dialogs(consent), {"capital_quote": "1500"}
    )

    assert command == StartBotCommand(
        "a00001", {"capital_quote": "1500"}, real_money_confirmed=True
    )
