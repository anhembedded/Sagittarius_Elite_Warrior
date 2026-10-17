"""`scripts/measure_startup.py` reads `python -X importtime` the way the owner compares builds (`PRO-014`).

The script is how the owner checks on the VPS what this repository can only show in a
container, so the one piece of logic in it - which lines of the report count - is held here.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.measure_startup import (
    Samples,
    report,
    top_level_import_seconds,
)

_REPORT = """\
import time: self [us] | cumulative | imported package
import time:       100 |        100 |   _frozen_importlib_external
import time:       200 |        900 |   binance.client
import time:       300 |       1000 | binance
import time:        50 |         50 | json
Traceback (most recent call last): not an import line
"""


def test_only_the_imports_nothing_else_started_are_summed() -> None:
    """A nested import's time is already inside its importer's cumulative time."""
    assert top_level_import_seconds(_REPORT) == (1000 + 50) / 1_000_000


def test_a_report_without_import_lines_is_zero() -> None:
    assert top_level_import_seconds("nothing\n") == 0.0


def test_two_checkouts_give_a_ratio_of_the_median_wall_times() -> None:
    this = Path("/new")
    other = Path("/old")
    fast = Samples(this, wall_seconds=[1.0, 2.0, 1.5], import_seconds=0.7)
    slow = Samples(other, wall_seconds=[2.0, 4.0, 3.0], import_seconds=1.5)

    text = report([fast, slow])

    assert "/old takes 2.00x as long as /new" in text
    assert "/old" in text
    assert "/new" in text
