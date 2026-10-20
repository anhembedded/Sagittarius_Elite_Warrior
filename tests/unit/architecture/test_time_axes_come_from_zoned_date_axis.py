"""A chart's time axis is a `ZonedDateAxisItem`, never a plain `pg.DateAxisItem`
(`BUG-240`, `BUG-243`).

A plain `DateAxisItem` labels in the machine's clock, so beside the crosshair and the tables,
which read in the display zone the person chose, it shows two answers to "what time is it".
`ZonedDateAxisItem` (`src/support/charting/chart_card/zoned_date_axis.py`) subclasses it and is
the one place that names the base class.

Scanned: every `*.py` under `src/`, by `ast`. Any reference to the name `DateAxisItem` outside the
subclass's own file fails (a construction, a subclass, `pg.DateAxisItem`, an import, aliased or
not); `ZonedDateAxisItem` does not, as its name differs.

Retire when: a charting library other than pyqtgraph draws the axes.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_ZONED_AXIS_FILE = "src/support/charting/chart_card/zoned_date_axis.py"
_PLAIN_AXIS = "DateAxisItem"


def _references(path: Path) -> list[int]:
    """Lines that name pyqtgraph's `DateAxisItem` by any route: a construction, a subclass, an
    attribute (`pg.DateAxisItem`) or an import, aliased or not. `ZonedDateAxisItem` is another name."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.Name)
            and node.id == _PLAIN_AXIS
            or isinstance(node, ast.Attribute)
            and node.attr == _PLAIN_AXIS
        ):
            lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            lines.extend(node.lineno for a in node.names if a.name == _PLAIN_AXIS)
    return lines


def test_no_chart_names_the_plain_date_axis() -> None:
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{line}"
        for path in sorted(_SRC_ROOT.rglob("*.py"))
        if path.relative_to(_REPO_ROOT).as_posix() != _ZONED_AXIS_FILE
        for line in _references(path)
    ]

    assert offenders == [], (
        "a plain DateAxisItem labels in the machine's clock, not the display zone; "
        "use ZonedDateAxisItem (zoned_date_axis.py):\n  " + "\n  ".join(offenders)
    )
