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

#: The two entry points, and `InstanceAccess` itself (its own `acquire`).
_ALLOWED = (
    "src/main.py",
    "src/presentation/ui/app_bootstrapper.py",
    "src/shell/composition_root.py",
    "src/infrastructure/instance/instance_access.py",
)


def _takes_the_lock(source: str, filename: str) -> bool:
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "acquire_instance_access":
            return True
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "acquire"
            and isinstance(func.value, ast.Name)
            and func.value.id == "InstanceAccess"
        ):
            return True
    return False


def _files_taking_the_lock() -> list[str]:
    return [
        path.relative_to(_REPO_ROOT).as_posix()
        for scanned in _SCANNED_DIRS
        for path in sorted(scanned.rglob("*.py"))
        if _takes_the_lock(path.read_text(encoding="utf-8"), str(path))
    ]


def test_only_the_entry_points_take_the_instance_lock() -> None:
    outside = [path for path in _files_taking_the_lock() if path not in _ALLOWED]

    assert outside == [], (
        f"{outside} take the instance lock. Only the entry points do "
        "(src/main.py, src/presentation/ui/app_bootstrapper.py); create_app() and "
        "build() take the answer as a parameter, so no test contends for it."
    )


def test_both_entry_points_do_take_it() -> None:
    taking = _files_taking_the_lock()

    assert "src/main.py" in taking
    assert "src/presentation/ui/app_bootstrapper.py" in taking


def test_the_guard_sees_a_call_it_should_refuse() -> None:
    assert _takes_the_lock("acquire_instance_access()", "x.py")
    assert _takes_the_lock("InstanceAccess.acquire(path)", "x.py")
    assert not _takes_the_lock("InstanceAccess.unguarded()", "x.py")
