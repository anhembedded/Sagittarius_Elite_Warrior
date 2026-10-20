"""A chart's time axis is a `ZonedDateAxisItem`, never a plain `pg.DateAxisItem`
(`BUG-240`, `BUG-243`).

A plain `DateAxisItem` labels in the machine's clock, so beside the crosshair and the tables,
which read in the display zone the person chose, it shows two answers to "what time is it".
`ZonedDateAxisItem` (`src/support/charting/chart_card/zoned_date_axis.py`) subclasses it and is
the one place that names the base class.

Scanned: every `*.py` under `src/`. A construction `DateAxisItem(...)` outside the subclass's
own file fails; `ZonedDateAxisItem(...)` does not, as its name differs.

Retire when: a charting library other than pyqtgraph draws the axes.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_ZONED_AXIS_FILE = "src/support/charting/chart_card/zoned_date_axis.py"
#: `DateAxisItem(` not preceded by a letter, so `ZonedDateAxisItem(` does not match.
_PLAIN_DATE_AXIS = re.compile(r"(?<![A-Za-z])DateAxisItem\(")


def test_no_chart_builds_a_plain_date_axis() -> None:
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{number}"
        for path in sorted(_SRC_ROOT.rglob("*.py"))
        if path.relative_to(_REPO_ROOT).as_posix() != _ZONED_AXIS_FILE
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _PLAIN_DATE_AXIS.search(line)
    ]

    assert offenders == [], (
        "a plain DateAxisItem labels in the machine's clock, not the display zone; "
        "use ZonedDateAxisItem (zoned_date_axis.py):\n  " + "\n  ".join(offenders)
    )
