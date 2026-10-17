"""`EPIC-038L` - `bot edit` on the running host runs the screen's own Save for one bot at rest.

The chain is the real one (`edit_host_world.py`): the host handler, the screen's edit and start, and
the Grid kind. The state gate, the venue (a mainnet bot needs no typed venue), the command lock and the
owner's incident are proven here; the judgement of keys and values is in
`test_bot_edit_for_the_host_validation.py`.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.edit_host_world import (
    AT_REST,
    FUTURES,
    NOT_AT_REST,
    S,
    V,
    a_host,
    settings_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    add_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
)

# ---- the edit ----------------------------------------------------------------------------------


@pytest.mark.parametrize("state", AT_REST)
def test_a_bot_at_rest_is_edited_by_the_screens_own_edit_and_lands_on_draft(
    state: BotLifecycleState,
) -> None:
    host = a_host(state)
    before = host.definition

    result = host.edit(settings_of(lower="90", upper="150"))

    assert result.accepted, result.message
    assert host.config == {**CONFIG, "lower": "90", "upper": "150"}
    assert host.state is S.DRAFT
    assert (host.definition.name, host.definition.kind) == (before.name, before.kind)
    assert (host.definition.venue, host.definition.symbol) == (
        before.venue,
        before.symbol,
    )
    assert host.dispatcher.dispatched == [
        EditBotCommand(BOT, before.name, {**CONFIG, "lower": "90", "upper": "150"})
    ]


def test_the_reply_shows_each_change_as_old_to_new_and_the_plan_reminder() -> None:
    host = a_host()

    result = host.edit(settings_of(lower="90", spacing="GEOMETRIC"))

    assert "lower 100 -> 90" in result.message
    assert "spacing ARITHMETIC -> GEOMETRIC" in result.message
    assert "upper" not in result.message.split(";")[0]
    assert "DRAFT (it was STOPPED)" in result.message
    assert "plan file" in result.message and "bot apply" in result.message


def test_a_parameter_the_bot_never_held_is_shown_as_unset() -> None:
    host = a_host(config=CONFIG)

    result = host.edit(settings_of(on_range_exit="close"))

    assert "on_range_exit (unset) -> close" in result.message


@pytest.mark.parametrize("state", NOT_AT_REST)
def test_a_bot_that_is_not_at_rest_is_refused_in_words_and_nothing_changes(
    state: BotLifecycleState,
) -> None:
    host = a_host(state)

    result = host.edit(settings_of(lower="90"))

    assert not result.accepted
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert state.value in result.message
    assert "DRAFT or STOPPED" in result.message
    assert "Nothing was changed" in result.message
    assert host.config == CONFIG
    assert host.state is state
    assert host.dispatcher.dispatched == []


@pytest.mark.parametrize(
    "state", [state for state in NOT_AT_REST if state is not S.STOPPING]
)
def test_a_bot_that_can_be_stopped_is_told_to_stop_it_first(
    state: BotLifecycleState,
) -> None:
    result = a_host(state).edit(settings_of(lower="90"))

    assert "`bot stop`" in result.message


def test_a_bot_that_is_already_stopping_is_told_to_wait_not_to_stop_it() -> None:
    result = a_host(S.STOPPING).edit(settings_of(lower="90"))

    assert "bot stop" not in result.message
    assert "Wait until it is STOPPED" in result.message


def test_an_unknown_bot_is_refused_not_found() -> None:
    result = a_host().edit(settings_of(lower="90"), bot_id="zzzzzz")

    assert result.refusal is BotRefusal.NOT_FOUND


# ---- the venue is no part of an edit -----------------------------------------------------------


@pytest.mark.parametrize("venue", [V.SPOT_MAINNET, V.FUTURES_MAINNET])
def test_a_mainnet_bot_is_edited_without_a_typed_venue_and_nothing_is_opened(
    venue: TradingVenue,
) -> None:
    host = a_host(S.STOPPED, venue, config=FUTURES)

    result = host.edit(settings_of(lower="90"))

    assert result.accepted, result.message
    assert host.config["lower"] == "90"
    assert host.world.session.ready_requests == 0
    assert host.runner.started == []


def test_a_futures_bot_changes_its_leverage_and_direction_as_a_pair() -> None:
    host = a_host(S.STOPPED, V.FUTURES_TESTNET, config=FUTURES)

    assert host.edit(settings_of(leverage="5")).accepted
    assert host.config["leverage"] == "5" and host.config["direction"] == "LONG"
    assert host.edit(settings_of(direction="SHORT")).accepted
    assert host.config["direction"] == "SHORT"


def test_a_spot_bot_cannot_be_given_a_leverage_without_a_direction() -> None:
    host = a_host(S.STOPPED, V.SPOT_TESTNET)

    result = host.edit(settings_of(leverage="3"))

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "direction is missing" in result.message
    assert host.config == CONFIG


# ---- concurrency and the journey ---------------------------------------------------------------


def test_the_edit_is_made_under_the_command_lock_a_start_holds() -> None:
    host = a_host()

    host.edit(settings_of(lower="90"))

    assert host.lock.taken == 1
    assert host.held_when_saved == [True]
    assert not host.lock.is_held


def test_a_refusal_releases_the_lock_for_the_next_command() -> None:
    host = a_host(S.RUNNING)

    host.edit(settings_of(lower="90"))

    assert not host.lock.is_held
    assert (
        host.edit(settings_of(lower="90"), bot_id="zzzzzz").refusal
        is BotRefusal.NOT_FOUND
    )


def test_the_owners_incident_a_start_refused_for_the_range_is_fixed_by_an_edit() -> (
    None
):
    """`bot start` was refused because the price sat below the range; `bot edit` lowers the range
    on the stopped bot and the same bot then starts, with no other bot touched."""
    out_of_range = {
        **CONFIG,
        "lower": "125",
        "upper": "160",
        "take_profit": "price:170",
    }
    host = a_host(S.STOPPED, config=out_of_range)
    bystander = "byst01"
    add_bot(host.world, bystander, S.RUNNING, venue=V.SPOT_TESTNET, symbol="ETHUSDT")
    refused = host.start()
    assert not refused.accepted and host.runner.started == []

    edited = host.edit(settings_of(lower="100", upper="140", take_profit="price:150"))
    started = host.start()

    assert edited.accepted, edited.message
    assert started.accepted, started.message
    assert host.runner.started == [BOT]
    assert host.world.store.load(BotId(bystander)).bot.state is S.RUNNING
