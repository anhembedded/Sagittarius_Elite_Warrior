"""Count member names that two screens (or surfaces) both define — the `EPIC-025` Phase 1 metric.

@par What it measures
`PRO-004` §1 measured **59** method names defined in both `screens/trading` and
`screens/dashboard` and in no other screen. Phase 1 of `EPIC-025` ends when that
number is **0** — the two screens have become surfaces that hang widgets one
module owns, so there is nothing left to define twice.

@par Why the scan covers old and new trees together
The independent design review (`Tasks/reports/EPIC-025_design_review.md` §7.1)
pointed out that a script scanning only `screens/` returns 0 the moment the two
packages are renamed, whether or not any duplication was removed. So this script
scans every UI package that exists — `presentation/ui/screens/*`,
`modules/*/ui`, `shell/surfaces/*` — and reports, per pair of packages, the
member names both define. Renaming a package moves its count; it cannot hide it.

@par Definition (fixed; do not "improve" it silently)
A *member* is a `def` directly inside a `class` body. A *duplicate* between two
packages A and B is a member name defined in A and in B **and in no third
package**. Dunder names are members too (`__init__` is excluded by the third
package rule in practice, never by hand). Free functions are not members.

@par The one amendment, PR 4.1b, and it is loud because that clause says to be
A member name is **not** counted for a package when a shared base class that
package actually subclasses declares it. Overriding an inherited method is the
*opposite* of duplication: the name is the base class's, the package had no
choice about it, and counting it punishes the very extraction this epic makes.

It was found rather than anticipated, twice. PR 4.1a moved `trading`'s six feeds
into `modules/trading/ui/` and the total rose 115 -> 116, the one name
responsible being `_subscribe` — `BaseFeed`'s, which PR 1.6c put in
`support/ui_kit` so every feed could share it. PR 4.1b then extracted
`RowTableModel` into `support/ui_kit`, removing four models' worth of real
duplication, and the total rose again on `_role_data`: the new base class's own
extension point, overridden by two of its four subclasses.

**Two wider rules were measured and rejected**, because a metric that excuses
duplication is worth nothing:

  · *Every `@abstractmethod` under `src/support/` and `src/core/`* (43 names) —
    PR 4.1a's first attempt at this. It is a proxy for "the base class declares
    it", and it failed on the first hook that was deliberately **not** abstract:
    `_role_data` has a `return None` default so that a table with no extra roles
    need not implement it.
  · *Every method of every class under `src/support/` and `src/core/`* (564
    names) — this drops the total to **104**, excusing ten pairs, because a
    support class somewhere happens to define `_build_ui`, `_apply` and
    `_choose`. Rejected on that measurement.

What is implemented is neither: for each UI package, read the base classes its
own classes name, keep those that are classes under `src/support/` or
`src/core/`, and exclude exactly those classes' method names — **for that
package only**. So `_role_data` leaves `data_management`'s and
`trading.ui`'s counts because both subclass `RowTableModel`, while
`selected_row`, which those two packages define independently, is **still
counted** and is the next real duplication to remove.

The baseline is re-measured on the pre-change tree under the amended definition
rather than lowered to fit the post-change number, so the ratchet still compares
like with like.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"

#: Every place a UI package can live, old tree and new tree alike. The glob is
#: relative to `src/`; the package name is the last path component.
UI_PACKAGE_GLOBS: tuple[str, ...] = (
    "presentation/ui/screens/*",
    "modules/*/ui",
    "shell/surfaces/*",
)

#: The pair Phase 1 must bring to zero.
PHASE_1_PAIR: tuple[str, str] = ("dashboard", "trading")

#: Where a *shared* base class may live. A base class inside a UI package is
#: that package's own, and excluding its names would let real duplication hide
#: behind a base class introduced for the purpose.
SHARED_ABSTRACTION_ROOTS: tuple[str, ...] = ("support", "core")


def _shared_base_members() -> dict[str, frozenset[str]]:
    """Class name -> its method names, for every class under the shared roots."""
    found: dict[str, set[str]] = {}
    for root in SHARED_ABSTRACTION_ROOTS:
        for py_file in (_SRC / root).rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                found.setdefault(node.name, set()).update(
                    item.name
                    for item in node.body
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                )
    return {name: frozenset(members) for name, members in found.items()}


def _base_class_names(package_dir: Path) -> set[str]:
    """Every name this package's classes inherit from, as written.

    Resolved by *name* rather than by import, because a metric that needed a
    working import graph could not run on a tree mid-move. A `Subscript` base
    (`RowTableModel[PositionRow]`) is unwrapped to its generic; an `Attribute`
    base (`QtCore.QObject`) contributes its attribute.
    """
    names: set[str] = set()
    for py_file in package_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                while isinstance(base, ast.Subscript):
                    base = base.value
                if isinstance(base, ast.Name):
                    names.add(base.id)
                elif isinstance(base, ast.Attribute):
                    names.add(base.attr)
    return names


def _inherited_member_names(package_dir: Path) -> frozenset[str]:
    """The names this package inherits from shared base classes it subclasses."""
    shared = _shared_base_members()
    inherited: set[str] = set()
    for base in _base_class_names(package_dir) & shared.keys():
        inherited |= shared[base]
    return frozenset(inherited)


def _package_dirs() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for pattern in UI_PACKAGE_GLOBS:
        for path in sorted(_SRC.glob(pattern)):
            if not path.is_dir() or path.name.startswith("__"):
                continue
            name = path.name if path.name != "ui" else f"{path.parent.name}.ui"
            found[name] = path
    return found


def _member_names(package_dir: Path) -> set[str]:
    names: set[str] = set()
    for py_file in package_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    names.add(item.name)
    return names


def measure() -> dict[str, object]:
    packages = _package_dirs()
    members = {
        name: _member_names(path) - _inherited_member_names(path)
        for name, path in packages.items()
    }
    owners: dict[str, set[str]] = defaultdict(set)
    for package, names in members.items():
        for name in names:
            owners[name].add(package)

    pairs: dict[str, list[str]] = {}
    for a, b in combinations(sorted(packages), 2):
        shared = sorted(name for name, who in owners.items() if who == {a, b})
        if shared:
            pairs[f"{a}+{b}"] = shared

    key = "+".join(sorted(PHASE_1_PAIR))
    return {
        "packages": {
            name: str(path.relative_to(_REPO_ROOT)) for name, path in packages.items()
        },
        "duplicates_by_pair": pairs,
        "phase_1_pair": key,
        "phase_1_count": len(pairs.get(key, [])),
        "defined_in_more_than_one_package": sum(
            1 for who in owners.values() if len(who) > 1
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--json", action="store_true", help="print the full measurement as JSON"
    )
    args = parser.parse_args(argv)
    result = measure()
    if args.json:
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        print()
        return 0
    print(f"UI packages scanned: {', '.join(sorted(result['packages']))}")
    print(
        f"member names defined in more than one package: {result['defined_in_more_than_one_package']}"
    )
    for pair, names in sorted(
        result["duplicates_by_pair"].items(), key=lambda kv: -len(kv[1])
    ):
        print(f"  {pair}: {len(names)}")
    print(f"Phase 1 metric ({result['phase_1_pair']} only): {result['phase_1_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
