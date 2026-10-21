"""Whatever the Bots tab does to a bot, the running host does too (`EPIC-045D`, the owner's rule of 2026-10-21).

The rule was dropped once already: `bot delete` was cut from `EPIC-038K` on 2026-10-17 and New bot never
had a host verb, so adding a designed bot cost a host restart. This guard keeps it from drifting again.

**What it scans.** Every `*Command` the Bots tab's UI imports from `bots/application/use_cases` is a
way the tab changes a bot. Each must be in `PARITY`: either `HostVerb` (the `HostControlAction` the
command file carries, the `bot <verb>` that sends it, both checked against the real tables) or
`Excluded` with a reason of at least a sentence. A tab command with neither fails here, and so does an
entry for a command the tab no longer imports.

**What it cannot see.** The tab's menu actions that dispatch no bot command are listed by hand in
`MENU_ACTIONS` below, each with the same two possible answers; the one list it checks against the code is
`BotAction`, the tab's lifecycle buttons, and the kind-specific toolbar commands.

**Gaps it records, not hides.** Two entries are exclusions the owner may want closed with a verb:
`ChangeBotVenueCommand` (a DRAFT's venue) and the strategy arm/disarm menu actions.

Retire when: the tab's actions are generated from one table that the host's verbs are also generated from.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import HostControlAction
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    _ControlVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import BOT_VERBS
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    all_kind_commands,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TAB = _REPO_ROOT / "src" / "modules" / "bots" / "ui"
_USE_CASES = "modules.bots.application.use_cases."
_MIN_REASON = 40


@dataclass(frozen=True, slots=True)
class HostVerb:
    """The tab command is reached on the host by `bot <verb>`, which sends this action."""

    verb: str
    action: HostControlAction


@dataclass(frozen=True, slots=True)
class Excluded:
    """The tab command has no host verb, and why that is acceptable (or an open gap)."""

    reason: str


#: Every `*Command` the Bots tab imports from the bots use cases, by name.
PARITY: dict[str, HostVerb | Excluded] = {
    "CreateBotCommand": HostVerb("add", HostControlAction.ADD),
    "EditBotCommand": HostVerb("edit", HostControlAction.EDIT),
    "StartBotCommand": HostVerb("start", HostControlAction.START),
    "PauseBotCommand": HostVerb("pause", HostControlAction.PAUSE),
    "ResumeBotCommand": HostVerb("resume", HostControlAction.RESUME),
    "StopBotCommand": HostVerb("stop", HostControlAction.STOP),
    "DeleteBotCommand": HostVerb("delete", HostControlAction.DELETE),
    "ConfirmBotResumeCommand": Excluded(
        "A HALTED bot's resume proposes a ladder that a person reads and confirms (decision D13), "
        "so `bot resume` refuses it; the host answers the confirmation in advance, for every "
        "HALTED or AWAITING_RECOVERY bot of the confirmed venues, with `run --resume-halted`."
    ),
    "ChangeBotVenueCommand": Excluded(
        "OPEN GAP. The tab moves a DRAFT that never ran to another venue. A plan names a bot by "
        "name and venue, so on the host the same result is `bot delete <id>` then `bot add` with "
        "the entry on the new venue; no single verb does it. Close it with a verb if the owner "
        "wants the move kept as one act."
    ),
}

#: The Bots menu and toolbar actions that dispatch no bot command, by hand (see the docstring).
MENU_ACTIONS: dict[str, HostVerb | Excluded] = {
    "Close the position at market": HostVerb("stop", HostControlAction.STOP),
    "Export plan...": Excluded(
        "It reads bots and writes a file, changing none; the host's equivalent is the read-only "
        "`bot export`, which works on the read-only copy beside a running host."
    ),
    "Arm strategy...": Excluded(
        "OPEN GAP. It arms a strategy of the strategy module on a venue, not a bot: there is no "
        "bot id and no host verb, and the host's `strategy` command runs one round and exits. "
        "Close it with a verb if the owner wants armed strategies run headless."
    ),
    "Disarm strategy...": Excluded(
        "OPEN GAP. The counterpart of Arm strategy; same reason, same way to close it."
    ),
}

#: The tab's lifecycle buttons and the bot command each one dispatches (`bot_commands.command_for`).
BUTTON_COMMAND: dict[BotAction, str] = {
    BotAction.START: "StartBotCommand",
    BotAction.PAUSE: "PauseBotCommand",
    BotAction.RESUME: "ResumeBotCommand",
    BotAction.CONFIRM_RESUME: "ConfirmBotResumeCommand",
    BotAction.STOP: "StopBotCommand",
    BotAction.SAVE: "EditBotCommand",
    BotAction.DELETE: "DeleteBotCommand",
}


def tab_commands() -> set[str]:
    """The `*Command` names the Bots tab's UI imports from the bots use cases."""
    found: set[str] = set()
    files = sorted(_TAB.rglob("*.py"))
    assert files, "the scan found no file under src/modules/bots/ui"
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and _USE_CASES in (node.module or ""):
                found.update(a.name for a in node.names if a.name.endswith("Command"))
    return found


def declared_bot_commands() -> set[str]:
    path = _REPO_ROOT / "src" / "config" / "cli_commands.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    return set(config["CLI_COMMANDS"]["bot"]["subparsers"]["commands"])


def parity_problems(
    tab: set[str],
    table: dict[str, HostVerb | Excluded],
    verbs: dict[str, HostControlAction],
    declared: set[str],
) -> list[str]:
    """Every way `table` fails to account for what the tab does; empty when it holds."""
    problems = [
        f"the tab dispatches {name} and PARITY has no row: give it a host verb or an "
        "Excluded row with its reason"
        for name in sorted(tab - table.keys())
    ]
    problems += [
        f"PARITY names {name}, which the tab no longer imports: remove the row"
        for name in sorted(table.keys() - tab)
    ]
    for name, row in sorted(table.items()):
        problems += _row_problems(name, row, verbs, declared)
    return problems


def _row_problems(
    name: str,
    row: HostVerb | Excluded,
    verbs: dict[str, HostControlAction],
    declared: set[str],
) -> list[str]:
    if isinstance(row, Excluded):
        short = len(row.reason.strip()) < _MIN_REASON
        return [f"{name}: an exclusion needs a reason of a sentence"] if short else []
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


def _control_verbs() -> dict[str, HostControlAction]:
    return {v.name: v.action for v in BOT_VERBS if isinstance(v, _ControlVerb)}


def test_every_bots_tab_command_has_a_host_verb_or_a_reasoned_exclusion() -> None:
    problems = parity_problems(
        tab_commands(), PARITY, _control_verbs(), declared_bot_commands()
    )

    assert problems == [], (
        "the Bots tab and the running host drifted (the owner's rule, 2026-10-21: whatever "
        "the UI does at runtime the VPS does too):\n  " + "\n  ".join(problems)
    )


def test_a_tab_command_with_no_row_is_caught() -> None:
    """The guard can fail: a command the tab gained and nobody mapped."""
    problems = parity_problems(
        tab_commands() | {"ArchiveBotCommand"},
        PARITY,
        _control_verbs(),
        declared_bot_commands(),
    )

    assert any("ArchiveBotCommand" in p for p in problems)


def test_a_row_for_a_command_the_tab_dropped_is_caught() -> None:
    problems = parity_problems(
        tab_commands() - {"DeleteBotCommand"},
        PARITY,
        _control_verbs(),
        declared_bot_commands(),
    )

    assert any("DeleteBotCommand" in p and "no longer" in p for p in problems)


def test_a_verb_that_sends_another_action_or_is_undeclared_is_caught() -> None:
    wrong = {**PARITY, "DeleteBotCommand": HostVerb("delete", HostControlAction.STOP)}
    problems = parity_problems(
        tab_commands(), wrong, _control_verbs(), declared_bot_commands() - {"delete"}
    )

    assert any("delete" in p and "sending STOP" in p for p in problems)
    assert any("not declared in cli_commands.json" in p for p in problems)


def test_an_exclusion_without_a_reason_is_caught() -> None:
    bare = {**PARITY, "ChangeBotVenueCommand": Excluded("no")}
    problems = parity_problems(
        tab_commands(), bare, _control_verbs(), declared_bot_commands()
    )

    assert any("ChangeBotVenueCommand" in p and "reason" in p for p in problems)


def test_every_lifecycle_button_dispatches_a_command_the_table_accounts_for() -> None:
    assert set(BUTTON_COMMAND) == set(BotAction), "a button was added: map its command"
    assert set(BUTTON_COMMAND.values()) <= set(PARITY)
    assert set(BUTTON_COMMAND.values()) <= tab_commands()


def test_every_menu_action_has_a_row_with_a_reason_or_a_real_verb() -> None:
    problems = []
    for name, row in MENU_ACTIONS.items():
        problems += _row_problems(name, row, _control_verbs(), declared_bot_commands())

    assert problems == []


def test_a_kind_toolbar_command_changes_no_bot_so_it_needs_no_verb() -> None:
    """Suggest from ATR/Bollinger fill the form of a bot that is not saved: nothing to send."""
    ids = {command.command_id for command in all_kind_commands()}

    assert ids == {
        "bots.bots.grid.suggest_from_atr",
        "bots.bots.grid.suggest_from_bollinger",
    }, (
        "a kind gained a toolbar command: does it change a bot? Map it or extend this list"
    )


def test_the_stop_that_closes_the_position_is_the_hosts_close_position_flag() -> None:
    path = Path(_REPO_ROOT) / "src" / "config" / "cli_commands.json"
    stop = json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]["bot"][
        "subparsers"
    ]["commands"]["stop"]

    assert "--close-position" in {arg["name"] for arg in stop["args"]}
