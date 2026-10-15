"""`BUG-219` - the Stop dialog offers only the choices the Stop use case accepts.

@details A Futures bot cannot be stopped with its position kept (`EPIC-039H`, decision O8), yet the
dialog preselected "Keep" and the use case then refused it in an error box. The dialog now asks the
venue profile the same question the handler does, so a choice that cannot run is disabled with its
reason before it is offered.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.stop_bot_dialog import (
    StopBotDialog,
    stop_question,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_bot_lifecycle_commands import (
    _RecordingRunner,
)

_ID = "abc123"
_CLOCK = FakeBotClock()


def _bot(venue: TradingVenue) -> Bot:
    definition = BotDefinition("grid", "grid", venue, "ETHUSDT", {"lower": "1"})
    return Bot(
        BotId(_ID), definition, BotLifecycle(BotLifecycleState.RUNNING), _CLOCK.now()
    )


def _snapshot(venue: TradingVenue, held: str = "0.596") -> BotSnapshot:
    progress = BotProgress(Decimal(0), 0, 0, Decimal(held), Decimal(2000), "", "")
    return replace(BotSnapshot.of(_bot(venue)), progress=progress)


def test_a_futures_bot_cannot_be_asked_to_keep_and_closes_by_default(qtbot) -> None:
    dialog = StopBotDialog(_snapshot(TradingVenue.FUTURES_TESTNET))
    qtbot.addWidget(dialog)

    assert not dialog.keep.isEnabled()
    assert "EPIC-039L" in dialog.keep_reason.text()
    assert dialog.sell.isChecked()
    assert dialog.choice() is ExposureHandling.CLOSE_AT_MARKET
    assert dialog.sell.text() == "Close the position at market"


def test_a_futures_stop_question_says_position_not_base() -> None:
    question = stop_question(_snapshot(TradingVenue.FUTURES_TESTNET))

    assert "It holds a 0.596 ETHUSDT position." in question
    assert "base" not in question
    assert "no position" in stop_question(
        _snapshot(TradingVenue.FUTURES_TESTNET, held="0")
    )


def test_a_spot_stop_dialog_is_unchanged(qtbot) -> None:
    dialog = StopBotDialog(_snapshot(TradingVenue.SPOT_TESTNET))
    qtbot.addWidget(dialog)

    assert dialog.keep.isEnabled()
    assert dialog.keep.isChecked()
    assert dialog.keep_reason.text() == ""
    assert dialog.choice() is ExposureHandling.KEEP
    assert dialog.sell.text() == "Sell the base at market"
    assert "It holds 0.596 ETHUSDT base." in stop_question(
        _snapshot(TradingVenue.SPOT_TESTNET)
    )


@pytest.mark.parametrize("venue", list(TradingVenue))
def test_the_dialog_and_the_handler_agree_on_keeping_for_every_venue(
    venue: TradingVenue, qtbot
) -> None:
    store = FakeBotStore()
    store.save(StoredBot(_bot(venue), {"cycles": 1}))
    runner = _RecordingRunner(store, _CLOCK)
    kept = StopBotCommandHandler(store, runner).execute(
        StopBotCommand(_ID, ExposureHandling.KEEP)
    )
    dialog = StopBotDialog(BotSnapshot.of(_bot(venue)))
    qtbot.addWidget(dialog)

    assert dialog.keep.isEnabled() is kept.accepted
    assert (dialog.choice() is ExposureHandling.KEEP) is kept.accepted
    closed = StopBotCommandHandler(store, _RecordingRunner(store, _CLOCK)).execute(
        StopBotCommand(_ID, ExposureHandling.CLOSE_AT_MARKET)
    )
    assert closed.accepted
