"""`EPIC-042B` - a hand-written set or comparison that names HALTED also answers for AWAITING_RECOVERY.

The lifecycle table makes the enable-rules and the sets derived from it (`PRICE_STREAM_STATES`,
`restarts_into_recovering`) answer for a new state by themselves. A set or a comparison written by
hand does not: the review of ADR 042 found a dozen of them, the worst would have skipped the
real-money confirmation of a mainnet Resume, and the review of this guard's first version found the
operator's health line (a tuple of strings outside `bots/`).

The guard reads `src/` with `ast`, expression by expression, so a word in a docstring does not count
and a file that names the new state elsewhere does not excuse a HALTED-only set in it:

  · in `src/modules/bots/`, each set, comparison or dict that names `<BotLifecycleState>.HALTED` (the
    class, or an alias assigned to it in that file) must also name `AWAITING_RECOVERY` or ask
    `RESUME_PROPOSES_STATES`;
  · in all of `src/`, each tuple, list, set, comparison or dict holding the string "halted" must also
    hold "awaiting_recovery".

An expression that rightly stays HALTED-only is in `_EXCEPTIONS` as `(file, symbol)` with the reason.
The exceptions only shrink: an entry that no longer matches an offending expression fails as stale.

Retire when: the lifecycle states are a closed `match` the type checker proves exhaustive.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"
_BOTS = _SRC / "modules" / "bots"

_ENUM = "BotLifecycleState"

#: (file relative to `src/`, enclosing symbol) -> why HALTED alone is right there.
_EXCEPTIONS: dict[tuple[str, str], str] = {
    (
        "modules/bots/application/kinds/grid/grid_facts.py",
        "GridFacts._apply_switch",
    ): "switch-on pays the cancel a cut-short start owes; only HALTED owes it",
    (
        "modules/bots/application/kinds/grid/start/grid_interrupted_start.py",
        "GridInterruptedStart.owed",
    ): "a start cut short owes a cancel and ends HALTED; AWAITING_RECOVERY never owes one",
    (
        "modules/bots/application/kinds/grid/watch/grid_rate_limit_pause.py",
        "GridRateLimitPause.after_task",
    ): "schedules the pause's resume for the bot the limit halted; the wait is halted first",
    (
        "modules/bots/application/services/lifecycle/bot_boot_recovery.py",
        "BotBootRecovery.run",
    ): "pays the cancel a cut-short start owes at boot; only HALTED owes it",
    (
        "modules/alerting/application/sources/bot_alert_source.py",
        "<module>",
    ): "the entry into the wait is deliberately silent; its recovery and stall have their own events (`EPIC-042D`)",
    (
        "modules/alerting/application/sources/bot_reason_routes.py",
        "<module>",
    ): "the states a reason's own kind is raised on entry to; the wait is silent on entry and a wait on a quiet price feed is told by its stall (`EPIC-036B2`)",
}

_SET_LIKE = (ast.Set, ast.Compare, ast.Dict)
_STRING_LIKE = (ast.Tuple, ast.List, ast.Set, ast.Compare, ast.Dict)


def _aliases(tree: ast.AST) -> frozenset[str]:
    """The names the file gives `BotLifecycleState`: itself, `from ... import X as Y`, `Y = X`."""
    found = {_ENUM}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found |= {a.asname for a in node.names if a.name == _ENUM and a.asname}
        elif (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id in found
        ):
            found |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return frozenset(found)


def _names_state(node: ast.AST, state: str, aliases: frozenset[str]) -> bool:
    return any(
        isinstance(n, ast.Attribute)
        and n.attr == state
        and isinstance(n.value, ast.Name)
        and n.value.id in aliases
        for n in ast.walk(node)
    )


def _answers(node: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Attribute) and n.attr == "AWAITING_RECOVERY")
        or (isinstance(n, ast.Name) and n.id == "RESUME_PROPOSES_STATES")
        for n in ast.walk(node)
    )


def _strings(node: ast.AST) -> set[str]:
    return {
        n.value.lower()
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _offends(node: ast.AST, aliases: frozenset[str], *, in_bots: bool) -> bool:
    """Whether this one expression names HALTED and not the wait."""
    if (
        in_bots
        and isinstance(node, _SET_LIKE)
        and _names_state(node, "HALTED", aliases)
        and not _answers(node)
    ):
        return True
    if isinstance(node, _STRING_LIKE):
        strings = _strings(node)
        return "halted" in strings and "awaiting_recovery" not in strings
    return False


def _scan(
    node: ast.AST,
    aliases: frozenset[str],
    scope: tuple[str, ...],
    *,
    in_bots: bool,
) -> list[tuple[str, int]]:
    """The outermost offending expression of each kind under `node`, with its symbol."""
    if isinstance(node, ast.BinOp) and _answers(node):
        return []  # `RESUME_PROPOSES_STATES | {...}` answers as a whole
    if _offends(node, aliases, in_bots=in_bots):
        return [(".".join(scope) or "<module>", getattr(node, "lineno", 0))]
    inner = scope + (node.name,) if isinstance(node, _SCOPES) else scope
    found: list[tuple[str, int]] = []
    for child in ast.iter_child_nodes(node):
        found += _scan(child, aliases, inner, in_bots=in_bots)
    return found


def offences(source: str, *, in_bots: bool = True) -> list[tuple[str, int]]:
    """(symbol, line) for each expression in `source` that names HALTED and not the wait."""
    tree = ast.parse(source)
    return _scan(tree, _aliases(tree), (), in_bots=in_bots)


def _files() -> Iterator[Path]:
    return (p for p in sorted(_SRC.rglob("*.py")) if "__pycache__" not in p.parts)


def _found() -> set[tuple[str, str]]:
    found = set()
    for path in _files():
        relative = path.relative_to(_SRC).as_posix()
        in_bots = _BOTS in path.parents
        for symbol, _line in offences(
            path.read_text(encoding="utf-8"), in_bots=in_bots
        ):
            found.add((relative, symbol))
    return found


def test_the_scan_finds_files() -> None:
    assert any(_BOTS in path.parents for path in _files())


def test_every_expression_naming_halted_answers_for_awaiting_recovery_or_is_excepted() -> (
    None
):
    unanswered = sorted(_found() - _EXCEPTIONS.keys())
    assert not unanswered, (
        "these expressions name HALTED but not AWAITING_RECOVERY (ADR 042 §2.4): add the state, "
        f"ask RESUME_PROPOSES_STATES, or explain in _EXCEPTIONS: {unanswered}"
    )


def test_every_exception_is_still_needed() -> None:
    stale = sorted(_EXCEPTIONS.keys() - _found())
    assert not stale, f"drop these from _EXCEPTIONS, they no longer need it: {stale}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("S = {BotLifecycleState.HALTED}", 1),
        ("S = {BotLifecycleState.HALTED, BotLifecycleState.AWAITING_RECOVERY}", 0),
        ("S = RESUME_PROPOSES_STATES | {BotLifecycleState.HALTED}", 0),
        ("S = {Other.HALTED}", 0),
        ("# BotLifecycleState.HALTED in a comment", 0),
        ("from m import BotLifecycleState as L\nS = {L.HALTED}", 1),
        ("A = BotLifecycleState\nS = {A.HALTED}", 1),
        ("def f(s):\n    return s is _S.HALTED", 0),
        ("def f(s):\n    return s is BotLifecycleState.HALTED", 1),
        ("T = ('running', 'halted')", 1),
        ("T = ('running', 'halted', 'awaiting_recovery')", 0),
        ("T = {'HALTED': 1}", 1),
    ],
)
def test_the_scan_reads_the_syntax_not_the_words(source: str, expected: int) -> None:
    assert len(offences(source)) == expected


def test_a_file_that_names_the_wait_elsewhere_does_not_excuse_a_halted_only_set() -> (
    None
):
    source = (
        "A = {BotLifecycleState.HALTED, BotLifecycleState.AWAITING_RECOVERY}\n"
        "B = {BotLifecycleState.HALTED}\n"
    )
    assert [line for _symbol, line in offences(source)] == [2]
