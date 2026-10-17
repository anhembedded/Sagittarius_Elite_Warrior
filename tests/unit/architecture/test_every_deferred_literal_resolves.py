"""Every `Deferred("package.module:attribute")` written in `src/` names something that exists.

**Why.** A path string escapes mypy, ruff and the import guards (`core/contracts/deferred.py`),
and `PRO-014` put many more of them on the boot path: the headless commands, the modules'
classes, the writable boot of the bots, the exchange adapters, the Parquet writer. A typo in
one is a crash on the first run that reaches it - `sync` on a server, never the unit tier -
so this resolves every literal in `src/`: the module imports, the attribute is there and is
callable. `test_deferred_targets_resolve.py` does the same for what the modules *contribute*;
this is the rest.

Retire when: `Deferred` is replaced by a mechanism the type checker follows.
"""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _literals() -> list[tuple[str, str]]:
    """(file:line, target) of every `Deferred("...")` call with a string literal."""
    found: list[tuple[str, str]] = []
    for path in sorted((_REPO_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Deferred"
                and node.args
            ):
                target = _constant(node.args[0])
                if target is not None:
                    where = f"{path.relative_to(_REPO_ROOT).as_posix()}:{node.lineno}"
                    found.append((where, target))
    return found


def _constant(node: ast.expr) -> str | None:
    """The string a plain literal (or an implicit concatenation of literals) gives; an
    f-string is `None` here and handled by `_resolved_constants`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _resolved_constants(
    unresolvable: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Targets assembled from a module-level string constant, `f"{_PREFIX}.mod:attr"`.

    An f-string with any other part cannot be resolved here; its `file:line` goes to
    `unresolvable`, so the guard states its own blind spot instead of skipping it."""
    found: list[tuple[str, str]] = []
    for path in sorted((_REPO_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {
            target.id: statement.value.value
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
            for target in statement.targets
            if isinstance(target, ast.Name)
        }
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Deferred"
                and node.args
                and isinstance(node.args[0], ast.JoinedStr)
            ):
                continue
            parts: list[str] = []
            for value in node.args[0].values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif (
                    isinstance(value, ast.FormattedValue)
                    and isinstance(value.value, ast.Name)
                    and value.value.id in constants
                ):
                    parts.append(constants[value.value.id])
                else:
                    if unresolvable is not None:
                        where = (
                            f"{path.relative_to(_REPO_ROOT).as_posix()}:{node.lineno}"
                        )
                        unresolvable.append(where)
                    break
            else:
                where = f"{path.relative_to(_REPO_ROOT).as_posix()}:{node.lineno}"
                found.append((where, "".join(parts)))
    return found


def _all_targets() -> list[tuple[str, str]]:
    return _literals() + _resolved_constants()


def test_no_deferred_path_is_beyond_what_this_guard_can_resolve() -> None:
    """A `Deferred(f"{local}.mod:X")` would be a typo class the guard silently skipped."""
    unresolvable: list[str] = []
    _resolved_constants(unresolvable)
    # `ModuleEntry._target` builds its path from the entry's own fields; every entry is loaded
    # by `test_module_declarations.test_every_entry_id_is_the_id_of_the_class_it_names`.
    unresolvable = [
        w for w in unresolvable if not w.startswith("src/shell/modules.py:")
    ]
    assert not unresolvable, (
        "Deferred paths built from something other than a module-level string constant "
        f"cannot be checked: {unresolvable}"
    )


def test_the_guard_has_a_subject() -> None:
    """`PRO-014` alone added more than a dozen; fewer means the scan lost its subject."""
    assert len(_all_targets()) >= 15


@pytest.mark.parametrize(("where", "target"), _all_targets())
def test_the_target_resolves_to_something_callable(where: str, target: str) -> None:
    module, _, attribute = target.partition(":")
    resolved = getattr(import_module(module), attribute)
    assert callable(resolved), f"{where}: {target} is not callable"
