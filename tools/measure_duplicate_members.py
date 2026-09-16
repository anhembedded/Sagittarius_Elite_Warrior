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

@par The one amendment, PR 4.1a, and it is loud because that clause says to be
A member name is **not** counted when a shared base class outside the UI
packages declares it `@abstractmethod`. Implementing one abstraction in two
packages is the *opposite* of duplication: it is the shared abstraction doing
its job, and counting it punishes the very move this epic is making.

It was found rather than anticipated. Moving `trading`'s six feeds into
`modules/trading/ui/` raised the total 115 -> 116, and the single name
responsible was `_subscribe` — `BaseFeed`'s `@abstractmethod`, which PR 1.6c put
in `support/ui_kit` so that every feed could share it. `modules/strategy/ui`'s
feed implements it too, so the moment a second module's `ui/` had a feed, the
tool reported the shared base class as duplication.

The exclusion is deliberately **computed, not a hand-list**, and deliberately
narrow: only `@abstractmethod` declarations under `src/support/` and `src/core/`
qualify. Qt's own mandated overrides (`rowCount`, `data`, `headerData`) are
**still counted**, because nothing in this repository declares them — and so is
the real duplication that PR 4.1a's first attempt exposed: four
`QAbstractTableModel` subclasses in two packages sharing `_display_text`,
`_sort_value`, `row_for` and `selected_row`, which is a sortable-table shape
written twice and is `EPIC-025E` section 3.5's to fix. The amendment must not be
widened to cover that; if it ever does, this metric has stopped measuring
anything.

The baseline was re-measured on the pre-move tree under the amended definition
rather than lowered to fit the post-move number, so the ratchet still compares
like with like.

Run from the repository root:

    python3 tools/measure_duplicate_members.py            # human-readable
    python3 tools/measure_duplicate_members.py --json     # machine-readable
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

#: Where a *shared* abstraction may live. A name declared `@abstractmethod`
#: inside one of these trees is a contract every implementer must spell the same
#: way, so two UI packages spelling it the same way is not duplication. Kept to
#: two roots on purpose: a base class inside a UI package would be that
#: package's own, and excluding its names would let real duplication hide behind
#: an `@abstractmethod` added for the purpose.
SHARED_ABSTRACTION_ROOTS: tuple[str, ...] = ("support", "core")


def _shared_abstract_member_names() -> frozenset[str]:
    """Every name declared `@abstractmethod` under `SHARED_ABSTRACTION_ROOTS`."""
    names: set[str] = set()
    for root in SHARED_ABSTRACTION_ROOTS:
        for py_file in (_SRC / root).rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if not isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        continue
                    if any(
                        isinstance(d, ast.Name) and d.id == "abstractmethod"
                        for d in item.decorator_list
                    ):
                        names.add(item.name)
    return frozenset(names)


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
    shared = _shared_abstract_member_names()
    members = {name: _member_names(path) - shared for name, path in packages.items()}
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
