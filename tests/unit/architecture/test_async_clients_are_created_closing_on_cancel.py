"""`BUG-263` - every `AsyncClient.create(...)` in `src/` sits inside `create_closing_on_cancel(...)`.

@details The library's `AsyncClient.create` leaks its HTTP session when the creating task is cancelled
(`closing_on_cancel.py`), and the leak shows as `Unclosed client session` at host stop. The sanity
tier replaces the client with a mock, so nothing else would catch a fourth stream that calls it
bare. A call is allowed when an enclosing call is `create_closing_on_cancel`.

Retire when: python-binance closes its session for `BaseException` in `AsyncClient.create`, or the
app stops using its async client.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.git_tracked_paths import (
    tracked_paths,
)

_REPO = Path(__file__).resolve().parents[3]
_WRAPPER = "create_closing_on_cancel"


def _is_create_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "AsyncClient"
    )


def _is_wrapper_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _WRAPPER
    )


def _bare_creations(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    bare = []
    for node in ast.walk(tree):
        if not _is_create_call(node):
            continue
        ancestor = parents.get(node)
        while ancestor is not None and not _is_wrapper_call(ancestor):
            ancestor = parents.get(ancestor)
        if ancestor is None:
            bare.append(node.lineno)
    return bare


def _source_files() -> list[Path]:
    """Every tracked Python file under `src/` (the git index, so no registry row is needed)."""
    return [
        _REPO / name
        for name in sorted(tracked_paths(_REPO))
        if name.startswith("src/") and name.endswith(".py")
    ]


def test_no_async_client_is_created_bare() -> None:
    offenders = {
        f"{path.relative_to(_REPO)}:{line}"
        for path in _source_files()
        for line in _bare_creations(path)
    }

    assert offenders == set()


def test_the_scan_sees_the_streams_that_create_one() -> None:
    wrapped = {
        path.name
        for path in _source_files()
        if _WRAPPER in path.read_text(encoding="utf-8")
        and "AsyncClient.create" in path.read_text(encoding="utf-8")
    }

    assert {
        "futures_user_data_stream.py",
        "spot_user_data_stream.py",
        "binance_websocket_service.py",
    } <= wrapped
