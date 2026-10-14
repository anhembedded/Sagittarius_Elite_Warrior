"""`BUG-204` — what the Bots screen says of a RECOVERING bot, and what its Resume sends.

@details A RECOVERING bot's rows are the ladder as saved: nothing has listened to
the exchange since the app started, so a row may be an order that has since
filled. The Orders panel says so beside the rows, and says nothing of the kind for
a bot that is listening. Resume, which the lifecycle table now declares for
RECOVERING, carries the real-money answer the use case asks for.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_activity_panels import (
    RECOVERING_ORDERS_NOTE,
    BotOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_commands import (
    command_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    dialogs_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_real_money_consent import (
    FakeRealMoneyConsent,
)

from .bots_screen_fixtures import stored


@pytest.fixture(autouse=True)
def _application(qapp: object) -> None:
    """A widget needs the application to exist."""


def _snapshot(state: BotLifecycleState) -> BotSnapshot:
    return BotSnapshot.of(stored("a00001", state).bot)


def _panel_showing(state: BotLifecycleState) -> BotOrdersPanel:
    model = BotsViewModel()
    panel = BotOrdersPanel(model)
    model.set_selected(_snapshot(state))
    return panel


def test_a_recovering_bots_orders_say_they_are_the_saved_ladder() -> None:
    panel = _panel_showing(BotLifecycleState.RECOVERING)

    assert panel.note.text() == RECOVERING_ORDERS_NOTE
    assert not panel.note.isHidden()
    assert "may have filled" in panel.note.text()


@pytest.mark.parametrize(
    "state",
    [
        BotLifecycleState.RUNNING,
        BotLifecycleState.PAUSED,
        BotLifecycleState.HALTED,
        BotLifecycleState.STOPPED,
    ],
)
def test_a_bot_that_listens_to_the_exchange_carries_no_such_note(
    state: BotLifecycleState,
) -> None:
    panel = _panel_showing(state)

    assert panel.note.text() == ""
    assert panel.note.isHidden()


def test_the_note_goes_when_the_bot_leaves_recovering() -> None:
    model = BotsViewModel()
    panel = BotOrdersPanel(model)
    model.set_selected(_snapshot(BotLifecycleState.RECOVERING))
    assert not panel.note.isHidden()

    # A list refresh keeps the selection and re-reads the bot: the detail follows.
    model.set_selected(_snapshot(BotLifecycleState.RUNNING))
    model.set_facts(None)

    assert panel.note.isHidden()


def test_resume_sends_the_real_money_answer_the_user_gave() -> None:
    consent = FakeRealMoneyConsent(agrees=True)

    command = command_for(
        BotAction.RESUME,
        _snapshot(BotLifecycleState.RECOVERING),
        dialogs_for(QWidget(), Mock(), consent),
    )

    assert command == ResumeBotCommand("a00001", real_money_confirmed=True)
