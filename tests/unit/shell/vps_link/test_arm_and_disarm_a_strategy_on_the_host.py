"""`EPIC-047E` (AC3, PR 3b) - Arm strategy… and Disarm strategy… in the VPS tab reach the host's own gate as its verbs.

The business promise: the strategy that is armed is the one the host's saved arming holds, so the tab asks only which venue;
a mainnet arm asks the real-money question by typing the venue and carries it for the host to judge; a cancel at either
question sends nothing; the host's words come back; and a second press while one waits does nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pytestqt.qtbot import QtBot
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    STRATEGY_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_requests import (
    request_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ArmStrategyForHostCommand,
    DisarmStrategyForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen import vps_backend
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    ARM_STRATEGY,
    DISARM_STRATEGY,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_command_ids import (
    vps_command_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.disarm_choice import (
    VenueQuestion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.host_strategies import (
    ARM_TITLE,
    HostStrategies,
    HostStrategyPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.bots_screen.bots_answers import (
    Answers,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.bots_screen.bots_screen_fixtures import (
    HeldPool,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_screen import (
    VpsScreen,
    open_vps_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld

TESTNET = TradingVenue.FUTURES_TESTNET
MAINNET = TradingVenue.FUTURES_MAINNET


@dataclass
class _Picks(Answers):
    """Answers the venue question with a venue of the test's choice (`None` cancels)."""

    venue: TradingVenue | None = TESTNET

    def _choose_venue(self, choice: VenueQuestion) -> TradingVenue | None:
        self.asked.append(f"choose {choice.title}")
        return self.venue


def _told(vps: VpsScreen) -> list[str]:
    log = vps.screen.view.output_log
    return [log.index(row).data(log.MessageRole) for row in range(log.rowCount())]


def _press(vps: VpsScreen, qtbot: QtBot, command: str) -> None:
    vps.actions.action(vps_command_id(command)).trigger()
    vps.screen.settle()
    qtbot.wait(50)  # the answer reaches the UI thread by a queued signal


def test_the_commands_become_the_hosts_arm_and_disarm_verbs() -> None:
    assert request_of(
        ArmStrategyForHostCommand("futures_mainnet", "futures_mainnet"), {}
    ) == HostControlRequest(
        HostControlAction.ARM_STRATEGY,
        STRATEGY_SUBJECT,
        "futures_mainnet",
        strategy_venue="futures_mainnet",
    )
    assert request_of(
        DisarmStrategyForHostCommand("spot_testnet"), {}
    ) == HostControlRequest(
        HostControlAction.DISARM_STRATEGY,
        STRATEGY_SUBJECT,
        strategy_venue="spot_testnet",
    )


def test_arming_on_a_testnet_reaches_the_host_without_a_question_and_says_its_words(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    tab.host.door.reply = HostControlReply(
        HostControlStatus.DONE, "the strategy was armed (see `bot list`)", "c" * 32
    )
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=TESTNET))

    _press(vps, qtbot, ARM_STRATEGY)

    (_, request, _) = tab.host.door.sent[0]
    assert request.action is HostControlAction.ARM_STRATEGY
    assert request.strategy_venue == TESTNET.value
    assert request.confirmed_venue is None
    assert any("the strategy was armed" in line for line in _told(vps))


def test_arming_on_mainnet_asks_the_typed_question_and_carries_the_venue_for_the_host_to_judge(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot, monkeypatch
) -> None:
    asked: list[tuple[TradingVenue, str]] = []

    def typing(venue: TradingVenue, action: str) -> str | None:
        asked.append((venue, action))
        return venue.confirmation_word

    monkeypatch.setattr(vps_backend, "ask_typed_venue", typing)
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=MAINNET))

    _press(vps, qtbot, ARM_STRATEGY)

    (_, request, _) = tab.host.door.sent[0]
    assert [venue for venue, _ in asked] == [MAINNET]
    assert request.confirmed_venue == MAINNET.value


def test_a_wrong_word_at_the_real_money_question_sends_nothing(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot, monkeypatch
) -> None:
    monkeypatch.setattr(vps_backend, "ask_typed_venue", lambda venue, action: "yes")
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=MAINNET))

    _press(vps, qtbot, ARM_STRATEGY)

    assert tab.host.door.sent == []


def test_cancelling_the_venue_question_sends_nothing_for_either_command(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=None))

    _press(vps, qtbot, ARM_STRATEGY)
    _press(vps, qtbot, DISARM_STRATEGY)

    assert tab.host.door.sent == []


def test_disarming_reaches_the_host_and_asks_no_real_money_question(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot, monkeypatch
) -> None:
    monkeypatch.setattr(
        vps_backend,
        "ask_typed_venue",
        lambda venue, action: (_ for _ in ()).throw(AssertionError("asked")),
    )
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=MAINNET))

    _press(vps, qtbot, DISARM_STRATEGY)

    (_, request, _) = tab.host.door.sent[0]
    assert request.action is HostControlAction.DISARM_STRATEGY
    assert request.strategy_venue == MAINNET.value
    assert request.confirmed_venue is None


def test_a_host_refusal_is_told_in_the_hosts_words_and_the_commands_free_again(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    tab.host.door.reply = HostControlReply(
        HostControlStatus.REFUSED, "No saved arming exists on this venue.", "c" * 32
    )
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=TESTNET))

    _press(vps, qtbot, ARM_STRATEGY)

    assert "No saved arming exists on this venue." in _told(vps)
    assert vps.actions.action(vps_command_id(ARM_STRATEGY)).isEnabled()
    assert vps.actions.action(vps_command_id(DISARM_STRATEGY)).isEnabled()


def test_while_one_command_waits_both_are_off_and_a_second_arm_sends_nothing(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=TESTNET))

    vps.actions.action(
        vps_command_id(ARM_STRATEGY)
    ).trigger()  # queued on the pool, not yet run
    assert not vps.actions.action(vps_command_id(ARM_STRATEGY)).isEnabled()
    assert not vps.actions.action(vps_command_id(DISARM_STRATEGY)).isEnabled()
    vps.screen.presenter.strategies.arm()  # a second way in, as a nested event loop could give
    vps.screen.settle()
    qtbot.wait(50)

    assert len(tab.host.door.sent) == 1
    assert vps.actions.action(vps_command_id(ARM_STRATEGY)).isEnabled()


def test_with_the_link_down_nothing_is_sent_and_the_person_is_told_why(
    tmp_path: Path, qtbot: QtBot
) -> None:
    tab = VpsTabWorld(hold_after_cut=True).start()
    vps = open_vps_screen(tmp_path, qtbot, tab, _Picks(venue=TESTNET))
    tab.cut()
    tab.wait_down()

    _press(vps, qtbot, ARM_STRATEGY)
    tab.stop()

    assert tab.host.door.sent == []
    assert any(
        "not connected" in line.lower() or "disconnected" in line.lower()
        for line in _told(vps)
    )


class _Recorder(ICommandDispatcher):
    def __init__(self) -> None:
        self.sent: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.sent.append(input_dto)
        return BotCommandResult(accepted=True, message="ok")


def test_a_command_that_went_out_while_a_question_was_open_is_not_followed_by_a_second(
    qtbot: QtBot,
) -> None:
    """The venue question runs a nested event loop; whatever went out meanwhile wins and the answered one is dropped."""
    pool, recorder, told = HeldPool(), _Recorder(), []
    holder: list[HostStrategies] = []

    def choose(question: VenueQuestion) -> TradingVenue | None:
        if question.title == ARM_TITLE:
            holder[0].disarm()  # another way in, answered while this question is open
        return TESTNET

    strategies = HostStrategies(
        HostStrategyPorts(
            commands=recorder,
            threads=pool,
            venues=(TESTNET,),
            choose=choose,
            allow_real_money=lambda venue, action: True,
            set_status=lambda text, error: None,
            tell=told.append,
        )
    )
    holder.append(strategies)

    strategies.arm()
    pool.run_all()
    qtbot.wait(50)

    assert [type(command).__name__ for command in recorder.sent] == [
        "DisarmStrategyForHostCommand"
    ]
