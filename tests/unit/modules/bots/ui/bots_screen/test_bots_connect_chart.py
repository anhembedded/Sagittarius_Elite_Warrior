"""`EPIC-034D` — what the Connect step does to the bot's chart and its Live stream
command: off while the account is unread, kept (hidden) for the same bot, closed
for another. `EPIC-034G` handed this gate over; PR #417's re-review shaped it."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    COMMAND_PREFIX,
    RETRY_CONNECTION,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_command_id,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_command import (
    LIVE_STREAM,
)

from .bots_screen_fixtures import BotsScreen, stored
from .connect_screen_helpers import chart_shown, failure, fresh_snapshot, select


def _live_stream(screen: BotsScreen):
    return screen.actions.action(chart_command_id(COMMAND_PREFIX, LIVE_STREAM))


def test_go_live_is_not_offered_until_the_account_was_read(open_bots_screen) -> None:
    """`EPIC-034G` handed this gate to the Connect step: the Live stream command
    follows the chart in front, and while the account is unread there is none."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    select(screen, "a00001")
    assert not _live_stream(screen).isEnabled()

    screen.settle()
    assert _live_stream(screen).isEnabled()


def test_a_connection_that_is_lost_takes_go_live_away_again(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert _live_stream(screen).isEnabled()

    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    _re_read(screen)
    screen.settle()

    assert not _live_stream(screen).isEnabled()


def _re_read(screen: BotsScreen) -> None:
    """The timer's tick: the selected bot's account is read again."""
    screen.presenter._account._timer.timeout.emit()


def _the_chart(screen: BotsScreen):
    return screen.presenter._charts._chart


def test_a_retry_keeps_a_running_bots_chart_and_its_stream(open_bots_screen) -> None:
    """PR #417 re-review: locking hides the chart of the same bot, it does not
    destroy it, so a re-read of a healthy account costs the user nothing."""
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    chart = _the_chart(screen)
    assert chart is not None
    state = chart.live_state
    assert _live_stream(screen).isEnabled()

    _re_read(screen)
    # The re-read of a connected account never locks it while it runs.
    assert chart_shown(screen) and _live_stream(screen).isEnabled()
    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    screen.settle()

    assert not chart_shown(screen)
    assert not _live_stream(screen).isEnabled()
    assert _the_chart(screen) is chart  # hidden, not closed
    assert chart.live_state is state

    screen.account.answer_with(fresh_snapshot())
    screen.actions.action(RETRY_CONNECTION).trigger()
    screen.settle()

    assert _the_chart(screen) is chart
    assert chart_shown(screen)
    assert _live_stream(screen).isEnabled()


def test_selecting_another_bot_while_locked_closes_the_previous_bots_chart(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING), stored("b00002", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert _the_chart(screen) is not None
    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    _re_read(screen)
    screen.settle()

    select(screen, "b00002")

    assert _the_chart(screen) is None  # a00001's chart and stream were released
    assert not _live_stream(screen).isEnabled()
