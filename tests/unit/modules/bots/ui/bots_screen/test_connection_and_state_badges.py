"""`EPIC-043C`: the connection and the bot's state are told as an icon and a word, never the icon alone."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_panel import (
    BotPlanPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    ConnectView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.identity_strip import (
    IdentityStrip,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone

from .bots_screen_fixtures import NOW, stored


@pytest.mark.parametrize(
    ("state", "icon", "tone"),
    [
        (ReadinessState.NOT_CONNECTED, "circle-x", Tone.CAUTION),
        (ReadinessState.CONNECTING, "clock", Tone.NEUTRAL),
        (ReadinessState.FAILED, "circle-x", Tone.NEGATIVE),
        (ReadinessState.DESIGNING, "circle-check-big", Tone.POSITIVE),
        (ReadinessState.RUN_BLOCKED, "circle-check-big", Tone.POSITIVE),
        (ReadinessState.READY, "circle-check-big", Tone.POSITIVE),
    ],
    ids=lambda v: getattr(v, "name", str(v)),
)
def test_every_connection_state_has_an_icon_and_a_tone(state, icon, tone) -> None:
    look = ConnectView(state=state).look

    assert (look.icon, look.tone) == (icon, tone)


def _strip(qtbot, view: ConnectView) -> IdentityStrip:
    model = BotsViewModel()
    strip = IdentityStrip(model)
    qtbot.addWidget(strip)
    strip.show()
    model.set_selected(
        BotSnapshot.of(stored("a00001", S.DRAFT, name="alpha").bot, None)
    )
    model.set_connect(view)
    return strip


def test_the_identity_strip_says_the_connection_with_an_icon_beside_the_word(
    qtbot,
) -> None:
    failed = ConnectView(
        ReadinessState.FAILED, "Spot Testnet", "Not connected", "key refused"
    )
    connected = ConnectView(
        ReadinessState.DESIGNING, "Spot Testnet", "Connected", "50,000.00"
    )

    strip = _strip(qtbot, failed)
    assert strip.connection.text() == "Spot Testnet: Not connected · key refused"
    assert strip.connection._icon.isVisible()
    bad = bytes(strip.connection._icon.pixmap().toImage().constBits())
    strip._model.set_connect(connected)

    assert strip.connection.text().startswith("Spot Testnet: Connected")
    assert bytes(strip.connection._icon.pixmap().toImage().constBits()) != bad
    assert strip.status_label._icon.isVisible()
    assert strip.status_label.text() == "Bot venue: Spot Testnet, connected"


def _plan(qtbot) -> tuple[BotPlanPanel, BotsViewModel]:
    model = BotsViewModel()
    panel = BotPlanPanel(model)
    qtbot.addWidget(panel)
    panel.resize(520, 700)
    panel.show()
    return panel, model


def _select(model: BotsViewModel, state: S) -> None:
    bot = BotSnapshot.of(stored("a00001", state).bot, None)
    model.set_selected(bot)
    model.set_facts(bot_facts(bot, NOW))


def test_the_plan_docks_state_is_an_icon_and_its_word(qtbot) -> None:
    panel, model = _plan(qtbot)

    _select(model, S.HALTED)
    assert panel.state.text() == "Halted"
    assert panel.state._icon.isVisible()
    halted = bytes(panel.state._icon.pixmap().toImage().constBits())

    _select(model, S.RUNNING)
    assert panel.state.text() == "Running"
    assert bytes(panel.state._icon.pixmap().toImage().constBits()) != halted

    _select(model, S.DRAFT)
    assert panel.state.text() == "Draft"
    assert not panel.state._icon.isVisible()


def test_a_bot_awaiting_recovery_reads_as_words_in_the_plan_dock(qtbot) -> None:
    panel, model = _plan(qtbot)

    _select(model, S.AWAITING_RECOVERY)

    assert panel.state.text() == "Awaiting recovery"
