"""How much of its own look the app still paints by hand (ADR D21, HLD §11.4).

The target is an application that applies **no** stylesheet, palette or
third-party theme of its own: standard controls render in the platform's theme,
and colour appears only where it carries meaning. `EPIC-025` PR 0.2 removed the
one global sheet (`qdarktheme`); what is left is per-widget styling inside the
screens that are still waiting to be rebuilt, so it is retired the way this
repository retires anything large — as a **ratchet**, measured here and kept
shrink-only by `tests/unit/architecture/test_app_styling_only_shrinks.py`.

Four numbers, each with its own reason to exist:

| Number | Why it is counted separately |
| :--- | :--- |
| `apply_role` calls | the shared QSS builder in `kit/style.py`; disappears with `kit/` |
| `set_style_sheet` calls | a widget painting itself directly, the crudest form |
| `palette_files` | files that import `Palette` at all — the colour source itself |
| `qml_theme_refs` | `Theme.<token>` inside `.qml`; disappears with the last `.qml` |

Python is read with `ast` (`BOT-133`: the regex version flagged documentation);
`.qml` has no Python parser, so the QML count is the one regex here.

Run it: `python tools/measure_app_styling.py [--json]`
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

#: The one place allowed to build QSS, and the one place allowed to hold colour.
STYLE_BUILDER = "src/presentation/ui/kit/style.py"
PALETTE_MODULE = "src/presentation/ui/assets/palette.py"

_QML_THEME_REF = re.compile(r"\bTheme\.[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class StylingCensus:
    apply_role_calls: int
    apply_role_files: int
    set_style_sheet_calls: int
    set_style_sheet_files: int
    palette_files: int
    qml_theme_refs: int
    qml_files: int


def _python_files() -> Iterator[Path]:
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


def _called_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            names.append(func.attr)
        elif isinstance(func, ast.Name):
            names.append(func.id)
    return names


def measure() -> StylingCensus:
    apply_role_calls = set_style_sheet_calls = 0
    apply_role_files: set[str] = set()
    set_style_sheet_files: set[str] = set()
    palette_files: set[str] = set()

    for path in _python_files():
        relative = path.relative_to(_REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        if relative != PALETTE_MODULE and _imports_palette(tree):
            palette_files.add(relative)

        if relative == STYLE_BUILDER:
            continue  # the builder's own internals are not call sites
        for name in _called_names(tree):
            if name == "apply_role":
                apply_role_calls += 1
                apply_role_files.add(relative)
            elif name == "setStyleSheet":
                set_style_sheet_calls += 1
                set_style_sheet_files.add(relative)

    qml_files = sorted(_SRC_ROOT.rglob("*.qml"))
    qml_theme_refs = sum(
        len(_QML_THEME_REF.findall(path.read_text(encoding="utf-8")))
        for path in qml_files
    )

    return StylingCensus(
        apply_role_calls=apply_role_calls,
        apply_role_files=len(apply_role_files),
        set_style_sheet_calls=set_style_sheet_calls,
        set_style_sheet_files=len(set_style_sheet_files),
        palette_files=len(palette_files),
        qml_theme_refs=qml_theme_refs,
        qml_files=len(qml_files),
    )


def _imports_palette(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "Palette" for alias in node.names
        ):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.endswith("palette") for alias in node.names
        ):
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    census = measure()
    if args.json:
        print(json.dumps(asdict(census), indent=1, sort_keys=True))
        return
    print("App-level styling still painted by hand (ADR D21 — target: every number 0)")
    print(
        f"  apply_role calls      : {census.apply_role_calls} in {census.apply_role_files} files"
    )
    print(
        f"  setStyleSheet calls   : {census.set_style_sheet_calls} "
        f"in {census.set_style_sheet_files} files"
    )
    print(f"  files importing Palette: {census.palette_files}")
    print(
        f"  QML Theme.* references : {census.qml_theme_refs} in {census.qml_files} .qml files"
    )


if __name__ == "__main__":
    main()
