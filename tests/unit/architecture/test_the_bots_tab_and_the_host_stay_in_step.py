"""Whatever the Bots tab does to a bot, the running host does too (`EPIC-045D`, the owner's rule of 2026-10-21).

The rule was dropped once already: `bot delete` was cut from `EPIC-038K` on 2026-10-17 and New bot never
had a host verb, so adding a designed bot cost a host restart. This guard keeps it from drifting again.

**Two enumerations, both of the code, neither of an import shape.**
1. *Commands.* Every `*Command` class defined under `bots/application/use_cases/` that is not a host
   request (`*_for_host`, `*_for_operator`) is a way to change a bot. Each must be in `PARITY`: a `HostVerb`
   (the `HostControlAction` the command file carries, the `bot <verb>` that sends it, its declaration in
   `cli_commands.json` and its row in the host's executor, all checked) or an `Excluded` with a reason of
   a sentence. A command added under any name, imported any way, fails here until it is classified.
   Every row must also be a command the tab still refers to, so a stale row fails too.
2. *Menu.* Every command id `bots_commands(route)` contributes to the Bots mode must be a lifecycle
   button (checked against `BotAction`), New bot, a kind toolbar command, or a row of `MENU` with a
   `HostVerb`, an `Excluded` reason or a `ReadOnly` reason. A new menu command fails here.

**Open gaps are recorded, not hidden.** An `Excluded` reason that begins `OPEN GAP` is something the Bots
tab does at runtime that the host cannot yet do in one act. They are the owner's to close with a verb
(slice `EPIC-045G`); that slice deletes its exclusions and the guard then enforces the verb.

Retire when: the tab's actions and the host's verbs are generated from one table.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import HostControlAction
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    _ControlVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import BOT_VERBS
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    NEW_BOT,
    bots_commands,
    lifecycle_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    all_kind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_host_command_executor import (
    BotHostCommandExecutor,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    command,
)

from .bots_tab_host_parity_rows import (
    BUTTON_COMMAND,
    MENU,
    PARITY,
    Excluded,
    HostVerb,
    ReadOnly,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TAB = _REPO_ROOT / "src" / "modules" / "bots" / "ui"
_USE_CASES = _REPO_ROOT / "src" / "modules" / "bots" / "application" / "use_cases"
_MIN_REASON = 40
#: A use case folder with one of these endings is the host's request, not a way the tab changes a bot.
_HOST_REQUEST_SUFFIXES = ("_for_host", "_for_operator")


def defined_commands() -> set[str]:
    """The bot commands defined under `use_cases/`, host requests (`*_for_*`) left out."""
    found: set[str] = set()
    files = sorted(_USE_CASES.glob("*/*.py"))
    assert files, "the scan found no file under bots/application/use_cases"
    for path in files:
        if path.parent.name.endswith(_HOST_REQUEST_SUFFIXES):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("Command")
        )
    return found


def tab_references() -> set[str]:
    """Every `*Command` name the tab's UI mentions, however it got it."""
    files = sorted(_TAB.rglob("*.py"))
    assert files, "the scan found no file under src/modules/bots/ui"
    found: set[str] = set()
    for path in files:
        found |= command_names_in(path.read_text(encoding="utf-8"))
    return found


def command_names_in(source: str) -> set[str]:
    """Every `*Command` name `source` mentions: an import (aliased or not), a name, a dotted use."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.alias):
            found.add(node.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
    return {name for name in found if name.endswith("Command")}


def declared_bot_commands() -> set[str]:
    path = _REPO_ROOT / "src" / "config" / "cli_commands.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    return set(config["CLI_COMMANDS"]["bot"]["subparsers"]["commands"])


def _control_verbs() -> dict[str, HostControlAction]:
    return {v.name: v.action for v in BOT_VERBS if isinstance(v, _ControlVerb)}


class _Spy:
    """Stands for the application's dispatcher: counts what the executor asks for."""

    def __init__(self) -> None:
        self.asked: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:

        self.asked.append(input_dto)
        return BotCommandResult.done("abc123")


def _executor_reaches(action: HostControlAction) -> bool:
    """Whether the host's executor turns a command file of `action` into a request to the bots."""

    spy = _Spy()
    entry = NewBotEntry("a", "grid", "spot_testnet", "SOLUSDT")
    BotHostCommandExecutor(spy).execute(  # type: ignore[arg-type]
        command(action=action, entry=entry, to_venue="spot_mainnet")
    )
    return len(spy.asked) == 1


def parity_problems(
    defined: set[str],
    referenced: set[str],
    table: dict[str, HostVerb | Excluded],
    verbs: dict[str, HostControlAction],
    declared: set[str],
) -> list[str]:
    """Every way `table` fails to account for the bot commands; empty when it holds."""
    problems = [
        f"{name} is a bot command (defined under use_cases/) and PARITY has no row: give it a "
        "host verb or an Excluded row with its reason"
        for name in sorted(defined - table.keys())
    ]
    problems += [
        f"PARITY names {name}, which is no longer a bot command: remove the row"
        for name in sorted(table.keys() - defined)
    ]
    problems += [
        f"PARITY names {name}, which the tab no longer refers to: remove the row"
        for name in sorted((table.keys() & defined) - referenced)
    ]
    for name, row in sorted(table.items()):
        problems += _row_problems(name, row, verbs, declared)
    return problems


def _row_problems(
    name: str,
    row: HostVerb | Excluded | ReadOnly,
    verbs: dict[str, HostControlAction],
    declared: set[str],
) -> list[str]:
    if isinstance(row, (Excluded, ReadOnly)):
        short = len(row.reason.strip()) < _MIN_REASON
        return [f"{name}: a reason needs a sentence"] if short else []
    problems: list[str] = []
    if verbs.get(row.verb) is not row.action:
        problems.append(
            f"{name}: `bot {row.verb}` is not a control verb sending {row.action.name}"
        )
    if row.verb not in declared:
        problems.append(
            f"{name}: `bot {row.verb}` is not declared in cli_commands.json"
        )
    return problems


def menu_problems(
    ids: set[str], table: dict[str, HostVerb | Excluded | ReadOnly]
) -> list[str]:
    """Menu commands nobody classified, and rows for commands the menu lost."""
    known = (
        {lifecycle_id(action) for action in BotAction}
        | {NEW_BOT}
        | {command.command_id for command in all_kind_commands()}
        | table.keys()
    )
    problems = [
        f"the Bots menu has the command {name} and MENU does not classify it: is it a "
        "HostVerb, an Excluded gap or ReadOnly?"
        for name in sorted(ids - known)
    ]
    problems += [
        f"MENU names {name}, which the Bots menu no longer has: remove the row"
        for name in sorted(table.keys() - ids)
    ]
    return problems


def test_every_bot_command_has_a_host_verb_or_a_reasoned_exclusion() -> None:
    problems = parity_problems(
        defined_commands(),
        tab_references(),
        PARITY,
        _control_verbs(),
        declared_bot_commands(),
    )

    assert problems == [], (
        "the Bots tab and the running host drifted (the owner's rule, 2026-10-21: whatever "
        "the UI does at runtime the VPS does too):\n  " + "\n  ".join(problems)
    )


def test_a_new_bot_command_is_caught_however_the_tab_imports_it() -> None:
    """The guard can fail, and it does not depend on an import shape: the command is only defined."""
    problems = parity_problems(
        defined_commands() | {"ArchiveBotCommand"},
        tab_references(),
        PARITY,
        _control_verbs(),
        declared_bot_commands(),
    )

    assert any("ArchiveBotCommand" in p and "no row" in p for p in problems)


def test_the_tab_reference_scan_sees_an_alias_a_dotted_use_and_a_relative_import() -> (
    None
):
    """The loose scan the stale-row check rests on is not a copy of one import form."""
    seeded = (
        "import pkg.use_cases.archive_bot as ab\n"
        "from ...use_cases.archive_bot import ArchiveBotCommand as Archive\n"
        "from . import use_cases\n"
        "ab.RestoreBotCommand(1)\n"
    )

    assert command_names_in(seeded) == {"ArchiveBotCommand", "RestoreBotCommand"}


def test_a_row_for_a_command_that_is_gone_or_unused_is_caught() -> None:
    gone = parity_problems(
        defined_commands() - {"DeleteBotCommand"},
        tab_references(),
        PARITY,
        _control_verbs(),
        declared_bot_commands(),
    )
    unused = parity_problems(
        defined_commands(),
        tab_references() - {"DeleteBotCommand"},
        PARITY,
        _control_verbs(),
        declared_bot_commands(),
    )

    assert any("DeleteBotCommand" in p and "no longer a bot command" in p for p in gone)
    assert any("DeleteBotCommand" in p and "no longer refers" in p for p in unused)


def test_a_verb_that_sends_another_action_or_is_undeclared_is_caught() -> None:
    wrong = {**PARITY, "DeleteBotCommand": HostVerb("delete", HostControlAction.STOP)}
    problems = parity_problems(
        defined_commands(),
        tab_references(),
        wrong,
        _control_verbs(),
        declared_bot_commands() - {"delete"},
    )

    assert any("delete" in p and "sending STOP" in p for p in problems)
    assert any("not declared in cli_commands.json" in p for p in problems)


def test_an_exclusion_without_a_reason_is_caught() -> None:
    bare = {**PARITY, "ChangeBotVenueCommand": Excluded("no")}
    problems = parity_problems(
        defined_commands(),
        tab_references(),
        bare,
        _control_verbs(),
        declared_bot_commands(),
    )

    assert any("ChangeBotVenueCommand" in p and "reason" in p for p in problems)


def test_every_host_verb_is_reached_by_the_hosts_executor() -> None:
    reached = {
        row.action: _executor_reaches(row.action)
        for row in PARITY.values()
        if isinstance(row, HostVerb)
    }

    assert all(reached.values()), f"the executor has no row for: {reached}"


def test_every_lifecycle_button_dispatches_a_command_the_table_accounts_for() -> None:
    assert set(BUTTON_COMMAND) == set(BotAction), "a button was added: map its command"
    assert set(BUTTON_COMMAND.values()) <= set(PARITY)


def test_every_bots_menu_command_is_classified() -> None:
    ids = {c.command_id for c in bots_commands("x")}

    problems = menu_problems(ids, MENU)
    for name, row in MENU.items():
        if isinstance(row, HostVerb):
            problems += _row_problems(
                name, row, _control_verbs(), declared_bot_commands()
            )
        elif isinstance(row, Excluded):
            problems += _row_problems(name, row, {}, set())

    assert problems == [], "\n  ".join(problems)


def test_a_menu_command_nobody_classified_is_caught() -> None:
    ids = {c.command_id for c in bots_commands("x")} | {"bots.bots.archive"}

    assert any("bots.bots.archive" in p for p in menu_problems(ids, MENU))


def test_the_stop_that_closes_the_position_is_the_hosts_close_position_flag() -> None:
    """The Stop dialog's "Close the position at market" is `StopBotCommand` with an exposure choice."""
    path = _REPO_ROOT / "src" / "config" / "cli_commands.json"
    stop = json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]["bot"][
        "subparsers"
    ]["commands"]["stop"]

    assert "--close-position" in {arg["name"] for arg in stop["args"]}
