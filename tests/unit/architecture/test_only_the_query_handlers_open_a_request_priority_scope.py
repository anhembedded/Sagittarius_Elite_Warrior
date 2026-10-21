"""`BOT-224` — only the three query handlers open the request-priority scope.

**Why.** `RequestPriority` travels from a port's caller to the session by a scope the query
handler opens around its one client call (`contracts/request_priority.py`): the session sits
below `ITradingClient`, so no parameter carries it. A scope opened anywhere else (a service that
wraps a loop of reads, a screen, a bot) would give every request inside it the weight reserve,
which is for the reads that guard exits and nothing else, and no reader of the port would see it.
The three handlers are the whole list; a fourth read that guards an exit adds its handler here,
with its port parameter and its test.

Retire when: `ITradingClient` carries the priority as a parameter, or the weight reserve is gone.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED = frozenset(
    {
        "src/modules/trading/application/queries/get_open_positions/handler.py",
        "src/modules/trading/application/queries/get_open_orders/handler.py",
        "src/modules/trading/application/queries/get_mark_price/handler.py",
    }
)


def opens_the_scope(source: str) -> bool:
    """Whether `source` calls `prioritised(...)`."""
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "prioritised")
            or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "prioritised"
            )
        )
        for node in ast.walk(ast.parse(source))
    )


def _openers() -> set[str]:
    return {
        path.relative_to(_REPO_ROOT).as_posix()
        for path in (_REPO_ROOT / "src").rglob("*.py")
        if opens_the_scope(path.read_text(encoding="utf-8"))
    }


def test_the_scope_is_opened_by_the_three_handlers_and_nobody_else() -> None:
    assert _openers() == _ALLOWED


def test_the_scanner_can_fail() -> None:
    assert opens_the_scope(
        "with prioritised(RequestPriority.EXIT_GUARD):\n    read()\n"
    )
    assert opens_the_scope("with request_priority.prioritised(p):\n    read()\n")
    assert not opens_the_scope('"""prioritised(p)"""\nx = 1\n')
    assert not opens_the_scope("priority = current_priority()\n")
