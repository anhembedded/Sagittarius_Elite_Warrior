"""`EPIC-021F`/`EPIC-021G`/`EPIC-021K` — `OrderSubmissionMode.LIVE` may only
ever be referenced as a real expression (not a docstring/comment mention)
from `ExecuteOrderCommandHandler` or `EmergencyStopCommandHandler` — the
only two places in this app allowed to construct `FuturesTradingClient`
with `LIVE` (`EPIC-021G` §2.1: no shortcut from anywhere else down to a
real order; `EPIC-021K` §2.2 lifts the same restriction for exactly one
more file — an emergency close/cancel needs the same real client).

@details Scans by `ast` for an `Attribute` node
(`OrderSubmissionMode.LIVE` used as a value — a constructor argument, a
dict key, a comparison, ...), not plain text: a docstring or comment
*explaining* this rule necessarily has to spell out the name it
restricts, and flagging that would make the rule impossible to document.
Mirrors `test_only_the_session_factory_constructs_binance_client.py`'s
shape (`EPIC-021A`).

Originally a total ban (`EPIC-021F`, when nothing had a legitimate reason
to submit a real order yet) — `EPIC-021G` is the task that lifted it for
the first file, per its own task file §3; `EPIC-021K` is the second.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCANNED_DIRS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")
_ALLOWED_FILES = (
    _REPO_ROOT
    / "src"
    / "application"
    / "use_cases"
    / "trading"
    / "execute_order"
    / "handler.py",
    _REPO_ROOT
    / "src"
    / "application"
    / "use_cases"
    / "trading"
    / "emergency_stop"
    / "handler.py",
)


def _references_live_mode(source: str, filename: str) -> bool:
    tree = ast.parse(source, filename=filename)
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "LIVE"
        and isinstance(node.value, ast.Name)
        and node.value.id == "OrderSubmissionMode"
        for node in ast.walk(tree)
    )


def _files_referencing_live_mode() -> list[Path]:
    hits: list[Path] = []
    for scanned_dir in _SCANNED_DIRS:
        for path in sorted(scanned_dir.rglob("*.py")):
            if _references_live_mode(path.read_text(encoding="utf-8"), str(path)):
                hits.append(path)
    return hits


def test_only_the_two_allowlisted_handlers_use_live_submission_mode() -> None:
    hits = _files_referencing_live_mode()
    assert hits == sorted(_ALLOWED_FILES), (
        "OrderSubmissionMode.LIVE referenced outside ExecuteOrderCommandHandler/"
        "EmergencyStopCommandHandler: "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in hits if p not in _ALLOWED_FILES]}"
    )


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): prove the scanner fires on a
    real usage shape, and correctly ignores a docstring merely naming it."""
    assert _references_live_mode(
        "from x import OrderSubmissionMode\n\nmode = OrderSubmissionMode.LIVE\n",
        "<violation-fixture>",
    )
    assert not _references_live_mode(
        '"""Do not use OrderSubmissionMode.LIVE here."""\n',
        "<docstring-only-fixture>",
    )
