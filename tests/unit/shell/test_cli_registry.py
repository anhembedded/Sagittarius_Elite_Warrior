"""`EPIC-025` PR 1.3c-5 — the shell collects prompt commands, modules declare.

Three things are worth holding, and the third is the one a mistake would
actually reach a user through:

1. a declared command arrives in the table under the word the user types;
2. two modules claiming one word fails **at boot**, naming both, rather than
   letting whichever registered last quietly win the next time somebody types
   it;
3. the table is a stable order, so `help` and any log of what was collected
   read the same on every run.

`test_contribution_registry.py` next door holds the same three properties for
panels, which is the point: one mechanism, two registries, and a reader who
has understood either has understood both.
"""

from __future__ import annotations

import argparse
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
)
from Sagittarius_Elite_Warrior.src.shell.cli_registry import CliRegistry


class _Sync(ICliCommandHandler):
    @staticmethod
    def handle(args: argparse.Namespace, app: Any) -> None:
        del args, app


class _Stream(ICliCommandHandler):
    @staticmethod
    def handle(args: argparse.Namespace, app: Any) -> None:
        del args, app


def _descriptor(
    name: str,
    handler: type[ICliCommandHandler] = _Sync,
    contributor_id: str = "market_data",
) -> CliCommandDescriptor:
    return CliCommandDescriptor(
        name=name, handler=handler, contributor_id=contributor_id
    )


def test_an_empty_registry_has_an_empty_table() -> None:
    assert CliRegistry().handlers() == {}


def test_a_declared_command_reaches_the_table_under_its_typed_word() -> None:
    registry = CliRegistry()

    registry.declare(_descriptor("exchange-status", handler=_Stream))

    # The hyphen matters: this is the word the user types and the key
    # `cli_commands.json` spells, not a Python identifier.
    assert registry.handlers() == {"exchange-status": _Stream}


def test_two_modules_claiming_one_word_fails_and_names_both() -> None:
    """A command word is an identity, not a sort key — unlike a panel's
    `order`, where two modules picking 10 is normal. Failing here means boot,
    with a stack that names the module that made the mistake; failing later
    means a user typing `sync` and getting somebody else's command."""
    registry = CliRegistry()
    registry.declare(_descriptor("sync", contributor_id="market_data"))

    with pytest.raises(ContributionError) as clash:
        registry.declare(_descriptor("sync", handler=_Stream, contributor_id="trading"))

    message = str(clash.value)
    assert "sync" in message
    assert "market_data" in message
    assert "trading" in message
    # And the first claim stands: a refused declaration changes nothing.
    assert registry.handlers() == {"sync": _Sync}


def test_the_same_handler_under_two_words_is_fine() -> None:
    """An alias is not a clash. Only the word is an identity."""
    registry = CliRegistry()

    registry.declare(_descriptor("sync"))
    registry.declare(_descriptor("s"))

    assert registry.handlers() == {"s": _Sync, "sync": _Sync}


def test_the_table_is_sorted_not_insertion_ordered() -> None:
    registry = CliRegistry()

    registry.declare(_descriptor("stream", handler=_Stream))
    registry.declare(_descriptor("sync"))
    registry.declare(_descriptor("exchange-status"))

    assert list(registry.handlers()) == ["exchange-status", "stream", "sync"]


def test_owner_of_answers_who_declared_a_command_and_none_for_the_rest() -> None:
    registry = CliRegistry()
    registry.declare(_descriptor("sync", contributor_id="market_data"))

    assert registry.owner_of("sync") == "market_data"
    assert registry.owner_of("nonesuch") is None
