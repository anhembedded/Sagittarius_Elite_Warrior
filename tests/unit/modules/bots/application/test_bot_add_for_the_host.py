"""`EPIC-045A` - `bot add` on the running host runs the screen's own New bot for one plan entry.

The chain is the real one (`add_delete_host_world.py`): the host handler, the screen's create and
the Grid kind. What is proven: the bot lands DRAFT with the entry's parameters and nothing is started
or sent; every refusal creates nothing and says why; the command lock is held.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.add_bot_for_host import (
    AddBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AddBotForHostCommand,
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
    an_entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.edit_host_world import (
    settings_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    StubKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
    SYMBOL,
)


def test_an_entry_becomes_a_draft_bot_with_its_parameters_and_nothing_starts() -> None:
    host = a_host()

    result = host.add(an_entry())

    assert result.accepted, result.message
    stored = host.world.store.load(BotId(result.bot_id or ""))
    assert stored.bot.state is BotLifecycleState.DRAFT
    assert stored.bot.definition.name == "sol grid"
    assert (stored.bot.definition.kind, stored.bot.definition.symbol) == (
        "grid",
        SYMBOL,
    )
    assert stored.bot.definition.venue is TradingVenue.SPOT_TESTNET
    assert dict(stored.bot.definition.config) == CONFIG
    assert host.runner.started == []
    assert [type(c) for c in host.dispatcher.dispatched] == [CreateBotCommand]


def test_the_reply_names_the_new_id_and_how_to_start_it() -> None:
    host = a_host()

    result = host.add(an_entry())

    assert f"bot start {result.bot_id}" in result.message
    assert "DRAFT" in result.message
    assert "--confirm-venue" not in result.message


def test_a_mainnet_entry_is_added_without_a_typed_venue_and_the_reply_names_the_start_flag() -> (
    None
):
    host = a_host()

    result = host.add(an_entry(venue="spot_mainnet"))

    assert result.accepted, result.message
    assert "--confirm-venue spot_mainnet" in result.message
    assert host.world.store.load(BotId(result.bot_id or "")).bot.state is (
        BotLifecycleState.DRAFT
    )


def test_the_create_runs_under_the_command_lock() -> None:
    host = a_host()
    seen: list[bool] = []
    inner = host.dispatcher.handlers[CreateBotCommand]
    original = inner.execute

    def watching(command: CreateBotCommand):  # type: ignore[no-untyped-def]
        seen.append(host.lock.is_held)
        return original(command)

    inner.execute = watching  # type: ignore[method-assign]

    host.add(an_entry())

    assert seen == [True]
    assert not host.lock.is_held


@pytest.mark.parametrize(
    ("entry", "words"),
    [
        (an_entry(venue="spot_nowhere"), "not a venue"),
        (an_entry(venue="disabled"), "not a venue"),
        (an_entry(kind="martingale"), "no kind of bot"),
        (an_entry(lower="90", upper="80", grid_count="5"), "upper"),
        (an_entry(nonsense="1"), "not a parameter"),
        (an_entry(api_secret="x"), "secret"),
    ],
    ids=[
        "unknown-venue",
        "disabled-venue",
        "unknown-kind",
        "bad-range",
        "unknown-key",
        "secret-name",
    ],
)
def test_a_refused_entry_creates_nothing_and_says_why(entry, words: str) -> None:  # type: ignore[no-untyped-def]
    host = a_host()

    result = host.add(entry)

    assert not result.accepted
    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert words in result.message
    assert "Nothing was created" in result.message
    assert host.ids == []
    assert host.dispatcher.dispatched == []


def test_a_name_already_on_that_venue_is_refused_and_points_at_bot_edit() -> None:
    host = a_host()
    first = host.add(an_entry())

    again = host.add(an_entry())

    assert not again.accepted
    assert f"bot edit {first.bot_id}" in again.message
    assert host.ids == [first.bot_id]


def test_the_same_name_on_another_venue_is_another_bot() -> None:
    host = a_host()
    host.add(an_entry())

    other = host.add(an_entry(venue="spot_mainnet"))

    assert other.accepted, other.message
    assert len(host.ids) == 2


class _AnyParameters(StubKind):
    """A kind that reads every key, so only the host's own check stands between a credential and a file."""

    def parameter_problem(self, config, changed):  # type: ignore[no-untyped-def]
        return None


def test_a_parameter_named_like_a_credential_is_refused_even_by_a_kind_that_reads_it() -> (
    None
):
    host = a_host()
    handler = AddBotForHostCommandHandler(
        host.world.store,
        host.dispatcher,
        BotKindCatalog([_AnyParameters("grid")]),
        host.lock,
    )

    refused = handler.execute(
        AddBotForHostCommand(
            NewBotEntry(
                "sol grid", "grid", "spot_testnet", SYMBOL, settings_of(api_key="abc")
            )
        )
    )
    allowed = handler.execute(
        AddBotForHostCommand(
            NewBotEntry(
                "sol grid", "grid", "spot_testnet", SYMBOL, settings_of(lower="1")
            )
        )
    )

    assert refused.refusal is BotRefusal.INVALID_DEFINITION
    assert "api_key is named like a secret" in refused.message
    assert "abc" not in refused.message
    assert allowed.accepted
