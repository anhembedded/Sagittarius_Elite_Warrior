"""`PRO-014` - which bounded contexts a run builds: the ones a command names and what they need.

The closure is the property that matters: the Engine refuses a context whose declared
dependencies are missing, so "bots only" must come back as bots and its suppliers.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.shell.module_selection import select_modules
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES


def _ids(needed: set[str] | None) -> list[str]:
    return [entry.module_id for entry in select_modules(MODULES, needed)]


def test_nothing_named_builds_the_whole_list() -> None:
    assert select_modules(MODULES, None) == MODULES


def test_a_context_comes_with_the_contexts_it_depends_on() -> None:
    assert set(_ids({"bots"})) == {"market_data", "trading", "bots"}


def test_dependencies_are_followed_all_the_way_down() -> None:
    """operations -> bots, alerting; bots -> trading, market_data."""
    assert set(_ids({"operations"})) == {
        "market_data",
        "trading",
        "bots",
        "alerting",
        "operations",
    }


def test_a_context_nobody_needs_is_left_out() -> None:
    chosen = set(_ids({"bots"}))

    assert {"strategy", "backtesting", "alerting", "operations"}.isdisjoint(chosen)


def test_the_selection_keeps_the_list_s_own_order() -> None:
    """`contribute()` runs in list order and a rail's panels appear in it (`shell/modules.py`)."""
    listed = [entry.module_id for entry in MODULES]
    chosen = _ids({"operations", "bots"})

    assert chosen == [module_id for module_id in listed if module_id in chosen]


def test_every_context_selected_by_itself_closes_over_listed_contexts() -> None:
    listed = {entry.module_id for entry in MODULES}
    for entry in MODULES:
        assert set(_ids({entry.module_id})) <= listed


def test_a_name_that_is_no_context_is_refused_not_ignored() -> None:
    """A typo in `cli_commands.json` would otherwise boot a run missing what it asked for."""
    with pytest.raises(ValueError, match="no such bounded context: bot"):
        select_modules(MODULES, {"bot"})
