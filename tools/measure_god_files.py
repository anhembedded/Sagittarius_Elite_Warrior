"""How many `src/` files already exceed the 400-line split threshold.

`architecture-rule.md` §5.4 sets a hard ceiling — **>400 lines per file forces
a split** — but the rule was review-only (`[review: C7, D6, D7]`): nothing
stopped a file already over it from growing further. `BOT-144`'s independent
review named exactly this gap. This module measures the debt; the ratchet
that keeps it shrink-only is
`tests/unit/architecture/test_god_files_only_shrink.py`.

Scope is `src/` only, matching where this repository already gates production
code (mypy's `src`+`scripts`, the module-boundary guard). `tests/`/`tools/`
also exceed 400 lines in many places (`architecture-rule.md` §5.4 names them
too) but freezing that debt as well is a separate, much larger undertaking
than `BOT-144` asked for — left for a future task rather than folded in here
silently.

Unlike the styling census this mirrors (`measure_app_styling.py`), a **new**
violation is never accepted into the baseline: this rule's own remedy is to
split the file, not to grandfather it in, so
`test_god_files_only_shrink.py` fails a file crossing 400 for the first time
outright rather than asking for a baseline edit.

Run it: `python tools/measure_god_files.py [--json]`
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

#: `architecture-rule.md` §5.4.
LINE_CEILING = 400


def _python_files() -> Iterator[Path]:
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


def measure() -> dict[str, int]:
    """Every `src/*.py` file over the ceiling, keyed by its repo-relative path."""
    census: dict[str, int] = {}
    for path in _python_files():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > LINE_CEILING:
            census[path.relative_to(_REPO_ROOT).as_posix()] = line_count
    return census


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    census = measure()
    if args.json:
        print(json.dumps(census, indent=1, sort_keys=True))
        return
    print(
        f"src/ files over the {LINE_CEILING}-line ceiling (architecture-rule.md §5.4):"
    )
    for path, lines in sorted(census.items(), key=lambda item: -item[1]):
        print(f"  {lines:>5}  {path}")
    print(f"  {len(census)} file(s) total")


if __name__ == "__main__":
    main()
