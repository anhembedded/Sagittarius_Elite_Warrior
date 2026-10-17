"""`PRO-014` - a command's `"modules"` names real bounded contexts, and each set can be built.

`cli_commands.json` says which contexts a command needs; `create_app` selects them with their
suppliers (`shell/module_selection.py`). A name that is no context, or a set the Engine
refuses, would show up as a crash the first time that command runs on a server. This reads
the real file and builds every declared set's selection.

Retire when: the command table is derived from the modules' `declare_cli` and the needs are
checked where the descriptor is built.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE
from Sagittarius_Elite_Warrior.src.shell.module_selection import select_modules
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import MODULES_KEY


def _declarations(
    commands: Mapping[str, Any], prefix: tuple[str, ...] = ()
) -> Iterator[tuple[str, list[str]]]:
    for name, entry in commands.items():
        path = (*prefix, name)
        if MODULES_KEY in entry:
            yield " ".join(path), entry[MODULES_KEY]
        yield from _declarations(entry.get("subparsers", {}).get("commands", {}), path)


def _real_declarations() -> list[tuple[str, list[str]]]:
    document = json.loads(CLI_COMMANDS_FILE.read_text(encoding="utf-8"))
    return list(_declarations(document["CLI_COMMANDS"]))


def test_the_file_declares_some_needs() -> None:
    assert _real_declarations(), "no command declares its contexts any more"


def test_every_declared_context_is_listed_and_selectable() -> None:
    known = {entry.module_id for entry in MODULES}
    for command, needed in _real_declarations():
        assert isinstance(needed, list), command
        assert set(needed) <= known, f"{command} names {sorted(set(needed) - known)}"
        assert select_modules(MODULES, needed), command
