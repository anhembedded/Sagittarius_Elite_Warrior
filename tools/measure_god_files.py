"""How many files already exceed the 400-line split threshold, per tree.

`architecture-rule.md` §5.4 sets a hard ceiling (**>400 lines per file forces
a split**) for `src/` and `tests/` alike, but the rule was review-only
(`[review: C7, D6, D7]`): nothing stopped a file already over it from growing
further. `BOT-144`'s independent review named that gap for `src/`, and
`BOT-146` closed it for `tests/` after two reviews in a row found test files
that had grown past the ceiling. This module measures the debt per tree; the
ratchet that keeps it shrink-only is
`tests/unit/architecture/test_god_files_only_shrink.py`, with one baseline per
tree.

`tools/` is not measured. It is small, and no review has found it growing.

Unlike the styling census this mirrors (`measure_app_styling.py`), a **new**
violation is never accepted into a baseline: this rule's own remedy is to
split the file, not to grandfather it in, so
`test_god_files_only_shrink.py` fails a file crossing 400 for the first time
outright rather than asking for a baseline edit.

Run it: `python tools/measure_god_files.py [--root src|tests] [--json]`
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: The trees the ratchet covers, each with its own baseline.
MEASURED_ROOTS = ("src", "tests")

#: `architecture-rule.md` §5.4.
LINE_CEILING = 400


def _python_files(root: str) -> Iterator[Path]:
    for path in sorted((_REPO_ROOT / root).rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


def measure(root: str = "src") -> dict[str, int]:
    """Every `<root>/**/*.py` file over the ceiling, keyed by its repo-relative path.

    @throws ValueError `root` is not one of `MEASURED_ROOTS`.
    """
    if root not in MEASURED_ROOTS:
        raise ValueError(f"unmeasured root {root!r}; expected one of {MEASURED_ROOTS}")
    census: dict[str, int] = {}
    for path in _python_files(root):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > LINE_CEILING:
            census[path.relative_to(_REPO_ROOT).as_posix()] = line_count
    return census


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", choices=MEASURED_ROOTS, default="src")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    census = measure(args.root)
    if args.json:
        print(json.dumps(census, indent=1, sort_keys=True))
        return
    print(
        f"{args.root}/ files over the {LINE_CEILING}-line ceiling (architecture-rule.md §5.4):"
    )
    for path, lines in sorted(census.items(), key=lambda item: -item[1]):
        print(f"  {lines:>5}  {path}")
    print(f"  {len(census)} file(s) total")


if __name__ == "__main__":
    main()
