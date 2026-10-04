"""`EPIC-029H` precondition — the Bots tab drives the real Grid executor.

`test_grid_bot_against_fake_server.py` dispatches the use cases itself; this
file presses the tab's own buttons instead. The Bots screen is built on the
composed app's container (its real dispatcher, thread pool, bus and stores),
over the fake Binance server, and Start, Pause, Resume and Stop go from the
screen to the `EPIC-029E` executor and out to the exchange. Only the bot's
queue and pacer and the fake's missing websocket are substituted, as in
`grid_fake_exchange`. The screen's answers arrive on the thread pool, so each
step waits on a named condition (`qtbot.waitUntil`), never a sleep.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
    BotsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
)

S = BotLifecycleState
_WAIT_MS = 10_000


class _Screen:
    """The Bots tab on the app's container; Stop always sells the base."""

    def __init__(self, app: BootedApp, qtbot: Any) -> None:
        self.app = app
        self.qtbot = qtbot
        self.stops: list[str] = []
        self.view = BotsView()
        qtbot.addWidget(self.view)
        self.presenter = BotsPresenter(
            self.view,
            app.engine.context.container,
            dialogs=BotsDialogs(
                ask_new_bot=lambda _kinds, _venues: None,
                ask_stop=self._ask_stop,
                confirm_delete=lambda _bot: False,
            ),
        )

    def _ask_stop(self, bot: BotSnapshot) -> BaseHandling:
        self.stops.append(bot.bot_id)
        return BaseHandling.SELL_AT_MARKET

    def select(self, bot_id: str) -> None:
        model = self.view.model
        self.qtbot.waitUntil(
            lambda: any(bot.bot_id == bot_id for bot in model.bots), timeout=_WAIT_MS
        )
        model.select_requested.emit(bot_id)

    def press(self, action: BotAction) -> None:
        """Waits for the button to be enabled, as a person would, then clicks."""
        button = self.view.detail.action_buttons[action]
        self.qtbot.waitUntil(button.isEnabled, timeout=_WAIT_MS)
        button.click()

    def wait_for(self, bot_id: str, state: BotLifecycleState) -> None:
        self.qtbot.waitUntil(
            lambda: self.app.bot(bot_id).state is state, timeout=_WAIT_MS
        )


@pytest.fixture
def screen(exchange: FakeExchange, qtbot: Any) -> Iterator[_Screen]:
    with booted(exchange) as app:
        opened = _Screen(app, qtbot)
        yield opened
        opened.presenter.dispose()


def _created(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    return created.bot_id


def test_start_pause_resume_and_stop_from_the_tab_reach_the_exchange(
    screen: _Screen,
) -> None:
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)

    screen.press(BotAction.START)
    screen.wait_for(bot_id, S.RUNNING)

    placed = ladder(app.runtime(bot_id))
    assert placed
    assert resting(app.urls) == placed

    screen.press(BotAction.PAUSE)
    screen.wait_for(bot_id, S.PAUSED)

    # Paused keeps the resting orders and places nothing new.
    assert resting(app.urls) == placed

    screen.press(BotAction.RESUME)
    screen.wait_for(bot_id, S.RUNNING)

    assert resting(app.urls) == ladder(app.runtime(bot_id))

    screen.press(BotAction.STOP)
    screen.wait_for(bot_id, S.STOPPED)

    assert screen.stops == [bot_id]
    # The dialog's answer (sell the base) reached the executor, not only the
    # stop itself: on the fake both answers leave nothing resting.
    assert app.runtime(bot_id).sell_base_on_stop
    assert resting(app.urls) == {}
