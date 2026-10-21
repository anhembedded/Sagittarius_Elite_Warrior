"""`EPIC-045G` - `bot move` on the running host runs the screen's own Venue field for one DRAFT that never ran.

The chain is the real one (`add_delete_host_world.py`): the host handler, the screen's venue change and the
bot aggregate's own rule. What is proven: only a Spot DRAFT that never ran moves, and it keeps its id and its
parameters; every refusal changes nothing and says why; a move places and asks for no real money; the
command lock is held.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.add_delete_host_world import (
    a_host,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.edit_host_world import (
    NOT_AT_REST,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
)

S = BotLifecycleState
V = TradingVenue


def _venue_of(host) -> TradingVenue:  # type: ignore[no-untyped-def]
    return host.world.store.load(BotId(BOT)).bot.definition.venue


def test_a_draft_that_never_ran_moves_keeps_its_id_and_parameters_and_stays_draft() -> (
    None
):
    host = a_host()
    host.hold(S.DRAFT)

    result = host.move("spot_mainnet")

    assert result.accepted, result.message
    stored = host.world.store.load(BotId(BOT)).bot
    assert stored.definition.venue is V.SPOT_MAINNET
    assert dict(stored.definition.config) == CONFIG
    assert stored.state is S.DRAFT
    assert host.ids == [BOT]
    assert host.dispatcher.dispatched == [ChangeBotVenueCommand(BOT, V.SPOT_MAINNET)]


def test_the_reply_names_the_venue_the_start_flag_and_the_plan_file_that_is_the_operators() -> (
    None
):
    host = a_host()
    host.hold(S.DRAFT)

    result = host.move("spot_mainnet")

    assert "from spot_testnet to spot_mainnet" in result.message
    assert f"bot start {BOT} --confirm-venue spot_mainnet" in result.message
    assert "plan-file entry" in result.message


def test_a_move_to_a_testnet_needs_no_start_flag_in_the_reply() -> None:
    host = a_host()
    host.hold(S.DRAFT, venue=V.SPOT_MAINNET)

    result = host.move("spot_testnet")

    assert result.accepted, result.message
    assert "--confirm-venue" not in result.message


@pytest.mark.parametrize("state", NOT_AT_REST + (S.STOPPED,), ids=lambda s: s.value)
def test_a_bot_that_is_not_a_draft_does_not_move(state: BotLifecycleState) -> None:
    host = a_host()
    host.hold(state)

    result = host.move("spot_mainnet")

    assert not result.accepted
    assert result.refusal is BotRefusal.VENUE_FIXED
    assert "Nothing was moved" in result.message
    assert _venue_of(host) is V.SPOT_TESTNET


def test_a_draft_that_ran_once_does_not_move() -> None:
    host = a_host()
    host.hold(S.DRAFT, ran=True)

    result = host.move("spot_mainnet")

    assert result.refusal is BotRefusal.VENUE_FIXED
    assert _venue_of(host) is V.SPOT_TESTNET


def test_a_futures_bot_does_not_move() -> None:
    host = a_host()
    host.hold(S.DRAFT, venue=V.FUTURES_TESTNET)

    result = host.move("spot_mainnet")

    assert result.refusal is BotRefusal.VENUE_FIXED
    assert _venue_of(host) is V.FUTURES_TESTNET


@pytest.mark.parametrize("word", ["spot_nowhere", "disabled", ""])
def test_a_venue_this_build_does_not_have_is_refused_in_words(word: str) -> None:
    host = a_host()
    host.hold(S.DRAFT)

    result = host.move(word)

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "not a venue" in result.message
    assert host.dispatcher.dispatched == []


def test_the_venue_the_bot_is_already_on_is_refused_and_changes_nothing() -> None:
    host = a_host()
    host.hold(S.DRAFT)

    result = host.move("spot_testnet")

    assert not result.accepted
    assert "already on spot_testnet" in result.message
    assert host.dispatcher.dispatched == []


def test_a_move_that_would_give_two_bots_one_name_on_a_venue_is_refused() -> None:
    host = a_host()
    host.hold(S.DRAFT, bot_id="aaaaaa", name="sol grid")
    host.hold(S.DRAFT, bot_id="bbbbbb", name="sol grid", venue=V.SPOT_MAINNET)

    result = host.move("spot_mainnet", bot_id="aaaaaa")

    assert not result.accepted
    assert "bbbbbb" in result.message and "already has the name" in result.message
    assert host.dispatcher.dispatched == []


def test_the_same_name_on_another_venue_does_not_block_a_move() -> None:
    host = a_host()
    host.hold(S.DRAFT, bot_id="aaaaaa", name="sol grid")
    host.hold(S.DRAFT, bot_id="bbbbbb", name="sol grid", venue=V.FUTURES_TESTNET)

    result = host.move("spot_mainnet", bot_id="aaaaaa")

    assert result.accepted, result.message


def test_an_unknown_bot_is_refused_as_the_screen_refuses_it() -> None:
    result = a_host().move("spot_mainnet", bot_id="zzzzzz")

    assert result.refusal is BotRefusal.NOT_FOUND


def test_the_move_runs_under_the_command_lock() -> None:
    host = a_host()
    host.hold(S.DRAFT)
    seen: list[bool] = []
    inner = host.dispatcher.handlers[ChangeBotVenueCommand]
    original = inner.execute

    def watching(command: ChangeBotVenueCommand):  # type: ignore[no-untyped-def]
        seen.append(host.lock.is_held)
        return original(command)

    inner.execute = watching  # type: ignore[method-assign]

    host.move("spot_mainnet")

    assert seen == [True]
    assert not host.lock.is_held
