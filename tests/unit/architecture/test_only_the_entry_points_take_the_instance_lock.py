"""`EPIC-035H` — only the two entry points take the data root's instance lock.

@details The lock is per process: a second `acquire` in the same process finds
the first one's lock taken and answers read-only. So a test or a sanity boot
that built the app through code which took the lock would fight the process
that holds it, or fight itself. The lock is therefore taken in exactly two
places, `main.py`'s and `app_bootstrapper.py`'s `main()`, through
`acquire_instance_access()`; `create_app()` and `build()` take the answer as a
parameter and never contend, and every test run has its own `SEW_DATA_ROOT`
(`EPIC-030M`) besides.

Scans `src/` and `scripts/` by `ast` for a **call** to `acquire_instance_access`
or `InstanceAccess.acquire`.

`Retire when:` the entry points are replaced by one launcher that takes the lock
once and hands the access to both (this guard then names the launcher).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCANNED_DIRS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")

#: Where a call may stand: the two entry points call `acquire_instance_access()`,
#: and the composition root's function of that name is the only place that calls
#: `InstanceAccess.acquire`. Anything else, `create_app` included, is refused.
_ALLOWED_CALLS = {
    "src/main.py": {"main"},
    "src/presentation/ui/app_bootstrapper.py": {"main"},
    "src/shell/composition_root.py": {"acquire_instance_access"},
}
_NAMES = ("acquire_instance_access", "InstanceAccess")


def _aliases(tree: ast.AST) -> set[str]:
    """Names that stand for the lock-taking callables, whatever they are imported as."""
    names = set(_NAMES)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _NAMES and alias.asname:
                    names.add(alias.asname)
    return names


def _calls_in(source: str, filename: str) -> list[str]:
    """The enclosing function of every call that takes the lock ('' at module level)."""
    tree = ast.parse(source, filename=filename)
    names = _aliases(tree)
    found: list[str] = []

    def visit(node: ast.AST, enclosing: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                else enclosing
            )
            if isinstance(child, ast.Call) and _takes_the_lock_call(child, names):
                found.append(enclosing)
            visit(child, inner)

    visit(tree, "")
    return found


def _takes_the_lock_call(call: ast.Call, names: set[str]) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in names and func.id != "InstanceAccess"
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "acquire"
        and isinstance(func.value, ast.Name)
        and func.value.id in names
    )


def _calls_by_file() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for scanned in _SCANNED_DIRS:
        for path in sorted(scanned.rglob("*.py")):
            calls = _calls_in(path.read_text(encoding="utf-8"), str(path))
            if calls:
                result[path.relative_to(_REPO_ROOT).as_posix()] = calls
    return result


def test_only_the_entry_points_take_the_instance_lock() -> None:
    outside = {
        path: calls
        for path, calls in _calls_by_file().items()
        if not set(calls) <= _ALLOWED_CALLS.get(path, set())
    }

    assert outside == {}, (
        f"{outside} take the instance lock outside the places allowed. Only the "
        "entry points' main() do (through acquire_instance_access()); create_app() "
        "and build() take the answer as a parameter, so no test contends for it."
    )


def test_both_entry_points_do_take_it() -> None:
    by_file = _calls_by_file()

    assert by_file.get("src/main.py") == ["main"]
    assert by_file.get("src/presentation/ui/app_bootstrapper.py") == ["main"]


def test_the_guard_sees_a_call_it_should_refuse() -> None:
    assert _calls_in("def f():\n    acquire_instance_access()", "x.py") == ["f"]
    assert _calls_in("InstanceAccess.acquire(path)", "x.py") == [""]
    assert _calls_in(
        "from a import InstanceAccess as X\ndef g():\n    X.acquire(p)", "x.py"
    ) == ["g"]
    assert _calls_in(
        "from a import acquire_instance_access as take\ndef g():\n    take()", "x.py"
    ) == ["g"]
    assert _calls_in("InstanceAccess.unguarded()", "x.py") == []
