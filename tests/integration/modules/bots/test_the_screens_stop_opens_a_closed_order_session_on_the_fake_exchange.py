"""`BUG-274` - the Bots screen's Stop on a bot waiting for a closed order session opens it and finishes.

@details The owner's desktop: a HALTED Futures bot, the app started again (a start always leaves the
venue's order session closed), Stop pressed twice. The bot went HALTED -> STOPPING and stayed there:
`StopBotCommandHandler` never opened the session, the stop's budget registration was refused with
"the order session is not open", and nothing cancelled or closed. Resume, Start and the headless
`bot stop` open the session; the screen's Stop did not. The same mechanism holds a RECOVERING bot,
which this journey uses (a real restart over the fake Futures exchange, the session closed).

The command is built by the screen's own `command_for`, so the test fails if the screen stops
carrying the person's answer; an automated Stop (the loss cap, the host's shutdown policy) carries
none and still opens nothing: a late order must not undo an Emergency Stop.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
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
)

from .grid_fake_exchange import FakeExchange
from .test_a_recovering_futures_bot_resumes_under_the_position_a_host_stop_left_on_the_fake_exchange import (
    ETH,
    FUTURES,
    SYMBOL,
    BootedTwoVenues,
    _position,
    _restarted_with_two_bots_left,
)

S = BotLifecycleState


def _screen_stop(app: BootedTwoVenues, bot_id: str) -> BotCommandResult:
    """The click: the screen's dialogs answer "close the position", the real-money question yes."""
    dialogs = BotsDialogs(
        ask_new_bot=lambda _kinds, _venues: None,
        ask_stop=lambda _bot: ExposureHandling.CLOSE_AT_MARKET,
        confirm_delete=lambda _bot: False,
        ask_arm_strategy=lambda _question: None,
        choose_venue=lambda _choice: None,
        allow_real_money=lambda _venue, _what: True,
        ask_export_plan=lambda _bots, _selected: None,
        ask_plan_save_path=lambda _suggested: "",
    )
    stored = app.store.load(BotId(bot_id))
    snapshot = BotSnapshot.of(stored.bot, bot_progress(stored))
    command = command_for(BotAction.STOP, snapshot, dialogs)
    assert isinstance(command, StopBotCommand)
    answer = app.engine.dispatch(StopBotCommand, command)
    app.deliver()
    assert isinstance(answer, BotCommandResult)
    return answer


def test_the_screens_stop_opens_the_closed_session_and_the_bot_reaches_stopped(
    both_venues: FakeExchange,
) -> None:
    with _restarted_with_two_bots_left(both_venues) as (app, btc, eth):
        assert app.scopes[FUTURES].session_state.enabled is False

        answer = _screen_stop(app, btc)

        assert answer.accepted, answer.message
        assert app.scopes[FUTURES].session_state.enabled is True
        assert app.bot(btc).state is S.STOPPED, app.runtime(btc).reason_detail
        assert _position(app, SYMBOL) == 0 and app.resting(FUTURES, SYMBOL) == set()
        assert _position(app, ETH) > 0, "the other bot's position was not touched"
        assert app.bot(eth).state is S.RECOVERING, "another bot's Stop woke it"


def test_an_automated_stop_opens_no_session_and_waits_saying_how_to_open_it(
    both_venues: FakeExchange,
) -> None:
    """The loss cap and the host's shutdown policy dispatch `StopBotCommand` with no answer of a
    person's: a closed session stays closed (a late order must not undo an Emergency Stop), and the
    bot waits in STOPPING saying so."""
    with _restarted_with_two_bots_left(both_venues) as (app, btc, _eth):
        answer = app.engine.dispatch(
            StopBotCommand, StopBotCommand(btc, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(answer, BotCommandResult)
        assert answer.accepted, answer.message
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(btc).state is S.STOPPING
        assert "the order session is not open" in app.runtime(btc).reason_detail
        assert "press Stop" in app.runtime(btc).reason_detail
