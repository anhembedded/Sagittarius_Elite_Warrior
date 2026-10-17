"""`EPIC-038L` - `bot edit` refuses a key or a value the bot's kind cannot store, in words, and changes nothing."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotDefinition
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.edit_host_world import (
    S,
    V,
    a_host,
    settings_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)

# ---- validation --------------------------------------------------------------------------------


def test_an_unknown_key_is_refused_in_words_and_the_stopped_bot_stays_stopped() -> None:
    host = a_host(S.STOPPED)

    result = host.edit(settings_of(lower="90", lowr="1"))

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "lowr" in result.message and "not a parameter of a grid" in result.message
    assert host.config == CONFIG and host.state is S.STOPPED
    assert host.dispatcher.dispatched == []


@pytest.mark.parametrize(
    ("key", "value", "says"),
    [
        ("lower", "abc", "lower is not a number"),
        ("lower", "-1", "lower must be positive"),
        ("lower", "150", "upper must be above lower"),
        ("upper", "99", "upper must be above lower"),
        ("grid_count", "0", "grid_count must be at least 1"),
        ("grid_count", "2.5", "grid_count is not a whole number"),
        ("spacing", "LOG", "spacing is not ARITHMETIC or GEOMETRIC"),
        ("capital_quote", "0", "capital_quote must be positive"),
        ("stop_loss", "percent:100", "a stop_loss percent must be below 100"),
        ("take_profit", "5", "take_profit is not off, price:<p> or percent:<n>"),
    ],
)
def test_a_value_the_kind_cannot_read_is_refused_and_changes_nothing(
    key: str, value: str, says: str
) -> None:
    host = a_host(S.STOPPED)

    result = host.edit(settings_of(**{key: value}))

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert says in result.message and "Nothing was changed" in result.message
    assert host.config == CONFIG and host.state is S.STOPPED


def test_one_bad_setting_among_good_ones_refuses_the_whole_edit() -> None:
    host = a_host(S.STOPPED)

    result = host.edit(settings_of(lower="90", grid_count="0"))

    assert not result.accepted
    assert host.config == CONFIG and host.state is S.STOPPED


def test_a_set_that_changes_nothing_is_refused_and_a_stopped_bot_is_not_moved() -> None:
    host = a_host(S.STOPPED)

    result = host.edit(settings_of(lower="100", grid_count="4"))

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "nothing to change" in result.message
    assert host.state is S.STOPPED


def test_a_setting_that_repeats_a_key_is_refused() -> None:
    host = a_host()

    result = host.edit(
        (ParameterSetting("lower", "90"), ParameterSetting("lower", "95"))
    )

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "lower is set more than once" in result.message
    assert host.config == CONFIG


def test_an_edit_with_no_setting_is_refused() -> None:
    result = a_host().edit(())

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "at least one" in result.message


def test_more_settings_than_the_bound_are_refused() -> None:
    settings = tuple(
        ParameterSetting(f"p{i}", "1") for i in range(MAX_SETTINGS_PER_EDIT + 1)
    )

    result = a_host().edit(settings)

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert str(MAX_SETTINGS_PER_EDIT) in result.message


def test_a_kind_the_build_does_not_know_is_refused_not_guessed_at() -> None:
    host = a_host()
    stored = host.world.store.load(BotId(BOT))
    ghost = BotDefinition("ghost", "ghost", V.SPOT_TESTNET, SYMBOL, CONFIG)
    host.world.store.save(
        StoredBot(
            type(stored.bot)(
                stored.bot.bot_id, ghost, stored.bot.lifecycle, stored.bot.created_at
            ),
            {},
        )
    )

    result = host.edit(settings_of(lower="90"))

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "ghost" in result.message
