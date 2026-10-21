"""Every hand-written set of bot lifecycle states says where each state stands (`EPIC-044`, S7).

Seventeen files read `RUNNING` as "has a ladder", and a dozen constants name lifecycle states by
hand. A new state (`AWAITING_RECOVERY` in `EPIC-042`, `AWAITING_RANGE` in `EPIC-044`) is silently
outside every one of them until somebody reads each; the ADR that claimed "a guard that every set
classifies every state" cited one that did not exist. Three checks:

  1. **Complete.** Every set the scan finds in the bots, alerting and operations modules is a row
     of `state_set_classification.STATE_SETS` (a new set must be classified when it is written).
  2. **Classified.** Each row names the members and the states left out, and together they are
     every `BotLifecycleState`: a new state fails here until each set has been read.
  3. **True.** The set in the code is exactly the row's members.

A set is a module-level assignment of `set`/`frozenset` whose members are lifecycle states, as
`BotLifecycleState.X` (under any alias of that import) or as the state's string value.

Retire when: the lifecycle table derives every one of these sets (`bot_lifecycle_fsm_matrix.py`
holds them all), so no file names a state by hand.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.state_set_classification import (
    ALL_STATES,
    STATE_SETS,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOTS = ("bots", "alerting", "operations")
_STATE_NAMES = frozenset(state.name for state in BotLifecycleState)
_PACKAGE = "Sagittarius_Elite_Warrior"


def _aliases(tree: ast.Module) -> frozenset[str]:
    """The names `BotLifecycleState` goes by in this module: its own name where it is defined
    or imported, an `import ... as`, and a module-level `_S = BotLifecycleState`."""
    names = {"BotLifecycleState"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names |= {
                alias.asname
                for alias in node.names
                if alias.name == "BotLifecycleState" and alias.asname
            }
        elif (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id == "BotLifecycleState"
        ):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return frozenset(names)


def _members(value: ast.expr, aliases: frozenset[str]) -> frozenset[str]:
    found: set[str] = set()
    for node in ast.walk(value):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr in _STATE_NAMES
        ):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and node.value in _STATE_NAMES:
            found.add(str(node.value))
    return frozenset(found)


def _is_a_set(value: ast.expr) -> bool:
    if isinstance(value, ast.Set):
        return True
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in {"set", "frozenset"}
    ):
        return True
    return isinstance(value, ast.BinOp) and (
        _is_a_set(value.left) or _is_a_set(value.right)
    )


def scanned_state_sets() -> dict[str, frozenset[str]]:
    """`path::NAME` -> the states the set names, for each set found in the scanned modules."""
    found: dict[str, frozenset[str]] = {}
    for root in _ROOTS:
        for path in sorted((_REPO_ROOT / "src" / "modules" / root).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            aliases = _aliases(tree)
            for node in tree.body:
                name, value = _assignment(node)
                if name is None or value is None or not _is_a_set(value):
                    continue
                members = _members(value, aliases)
                if members:
                    found[f"{path.relative_to(_REPO_ROOT).as_posix()}::{name}"] = (
                        members
                    )
    return found


def _assignment(node: ast.stmt) -> tuple[str | None, ast.expr | None]:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    return None, None


def _live(key: str) -> frozenset[str]:
    path, name = key.split("::")
    module = importlib.import_module(
        f"{_PACKAGE}.{path.removesuffix('.py').replace('/', '.')}"
    )
    return frozenset(
        member.name if isinstance(member, BotLifecycleState) else str(member)
        for member in getattr(module, name)
    )


def test_the_scan_finds_the_sets_it_is_meant_to_guard() -> None:
    """An empty or shrunken scan would pass every check below (`testing-rule.md` §2)."""
    assert len(scanned_state_sets()) >= 20


def test_every_hand_written_state_set_is_classified() -> None:
    unclassified = sorted(set(scanned_state_sets()) - set(STATE_SETS))
    assert not unclassified, (
        f"classify these sets of lifecycle states in state_set_classification.py: "
        f"{unclassified}"
    )


def test_a_classified_set_still_exists() -> None:
    gone = sorted(set(STATE_SETS) - set(scanned_state_sets()))
    assert not gone, f"remove these rows, the sets are gone or no longer sets: {gone}"


def test_the_classification_names_every_lifecycle_state() -> None:
    assert ALL_STATES == _STATE_NAMES, "the registry's list of states is out of date"


@pytest.mark.parametrize("key", sorted(STATE_SETS))
def test_each_row_puts_every_state_on_one_side_of_its_set(key: str) -> None:
    members, excluded = STATE_SETS[key]

    assert members | excluded == ALL_STATES, (
        f"{key}: state(s) {sorted(ALL_STATES - members - excluded)} stand on neither side"
    )
    assert not members & excluded, f"{key}: {sorted(members & excluded)} on both sides"


@pytest.mark.parametrize("key", sorted(STATE_SETS))
def test_the_set_in_the_code_is_the_row_s_members(key: str) -> None:
    assert _live(key) == STATE_SETS[key][0]
