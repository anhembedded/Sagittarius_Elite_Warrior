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
    members = {name: _member_names(path) for name, path in packages.items()}
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
