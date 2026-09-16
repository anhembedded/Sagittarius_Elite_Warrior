"""Guard: a path meant to be the repository root must **be** the repository root.

`Path(__file__).resolve().parents[3]` is a directory hop count, and a hop count
is broken by any change of depth — which is every move `EPIC-025` makes. Twice
in two pull requests it broke something that no other check could see:

  · PR 1.6f — `chart_toolbar.py` built its QML path as
    `parents[2] / "qml" / "TimeframePicker" / ...`. `parents[2]` had been
    `presentation/ui`; after the move it was `src/support`, so the toolbar
    silently loaded nothing. Caught by importing every moved module, because
    the failure was a `RuntimeError` at import.
  · PR 1.6g — this file's neighbour,
    `test_indicator_script_conventions.py`, used `parents[3]` while it sat at
    `tests/unit/domain/`. Moved to `tests/unit/support/indicators/`, one level
    deeper, `parents[3]` became `tests/` and the guard went looking for
    `tests/src/binance_bot_module.py`. Caught by the gate — after a
    three-and-a-half-minute run.

The fix in both cases is the same and is cheap: find the root by a **landmark**
that only the root has. So this guard does not ban `parents[N]` — plenty of
uses reach a known sibling and are correct — it checks the one thing that can
be checked mechanically: **every expression the author named a root actually
resolves to the root.** A wrong hop count then fails in milliseconds, at the
file that has it, instead of somewhere downstream in whatever that path was
feeding.

Stdlib only, like the other document and path guards here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def _repo_root() -> Path:
    """By landmark, because this file is an example of its own rule."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()

#: Where to look. `src/`, `tests/`, `scripts/` and `tools/` are the trees this
#: repository moves; a hop count anywhere else is somebody else's problem.
_SCAN_ROOTS = ("src", "tests", "scripts", "tools")

#: A name whose value the author is claiming is a repository root. Matching by
#: name is the whole trick: the guard needs no import and no execution, only
#: the author's own statement of intent.
_ROOT_NAME = re.compile(r"^_?(REPO_ROOT|BOT_ROOT|PROJECT_ROOT|ROOT)$")

#: `Path(__file__).resolve().parents[N]` — the shape that rots.
_PARENTS_INDEX = re.compile(r"parents\[(\d+)\]")


def _python_files() -> list[Path]:
    return [
        path
        for root in _SCAN_ROOTS
        for path in sorted((_REPO_ROOT / root).rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _root_assignments() -> list[tuple[Path, int, str, int]]:
    """Every `<ROOT-ish name> = ...parents[N]` as
    `(path, line, name, hop_count)`."""
    found: list[tuple[Path, int, str, int]] = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            name = getattr(target, "id", None)
            if not name or not _ROOT_NAME.match(name):
                continue
            match = _PARENTS_INDEX.search(ast.unparse(node.value))
            if match:
                found.append((path, node.lineno, name, int(match.group(1))))
    return found


def test_every_counted_root_really_is_the_root() -> None:
    """The check both defects needed. `parents[N]` from a file at a known
    depth is arithmetic the reader has to redo in their head; this redoes it
    for them, and for every file at once."""
    offenders: list[str] = []
    for path, line, name, hops in _root_assignments():
        parents = path.resolve().parents
        resolved = parents[hops] if hops < len(parents) else None
        if resolved != _REPO_ROOT:
            rel = path.relative_to(_REPO_ROOT).as_posix()
            offenders.append(
                f"{rel}:{line}: {name} = ...parents[{hops}] resolves to "
                f"{resolved}, not {_REPO_ROOT}"
            )

    assert offenders == [], (
        "a name declared to be the repository root is not the repository "
        "root. A hop count breaks whenever the file's depth changes, which is "
        "every move this epic makes — find the root by a landmark instead:\n"
        "    for candidate in Path(__file__).resolve().parents:\n"
        '        if (candidate / "pyproject.toml").is_file():\n'
        "            return candidate\n\n" + "\n".join(offenders)
    )


def test_the_guard_has_a_subject() -> None:
    """Locked at "more than five" rather than an exact number: the count moves
    with every file that needs a root, and a ratchet on it would be noise.
    Zero would mean the naming convention changed and this guard reads
    nothing."""
    assignments = _root_assignments()

    assert len(assignments) > 5, (
        f"only {len(assignments)} counted-root assignment(s) found. Either the "
        "repository stopped doing this — good — or the names moved away from "
        f"{_ROOT_NAME.pattern} and this guard is inspecting nothing."
    )
