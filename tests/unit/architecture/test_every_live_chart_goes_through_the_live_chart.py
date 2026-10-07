"""`EPIC-034I` — every chart that shows live market prices is a `LiveCandleChart`.

The owner, 2026-10-07: *"tui kỳ vọng là sau này dù chart nào cũng làm như vậy"*
(I expect that from now on every chart behaves this way): the four states
(History, Connecting, Live, Error), the reason and the age. The Desk's chart,
the Market mode's tabs and the Bots mode's chart are all built on
`support/charting/live_chart/`; this guard is what keeps the next one from
wiring a stream into a `ChartCard` by hand and showing a chart that says
nothing when its stream is gone (the Bots chart did, until `EPIC-034G`).

The shapes it finds, and what it lets through by shape, are in
`live_chart_wiring.py`; `test_live_chart_wiring_probes.py` feeds each rule a
source it must catch and one it must let by.

What is scanned: every UI file under `src/` (`is_ui`, as the formatter and
venue-title guards read it), except the one package that **is** the wiring,
`support/charting/live_chart/`. Charts that never stream are not named here:
the Backtest and Grid backtest charts read stored candles and the Desk's
equity chart pushes equity samples, and none of them refers to a live source.

Retire when: charts stop being `ChartCard`s, or live prices reach the UI by a
path whose names this shape cannot see (then widen `LIVE_SOURCE_NAME` first).
"""

from __future__ import annotations

from pathlib import Path

from .live_chart_wiring import live_chart_classes, wiring_violations
from .test_display_values_go_through_the_formatter import is_ui

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
#: The one package that wires a candle feed into a chart: the guard's subject
#: is everything else.
_LIVE_CHART_PACKAGE = "src/support/charting/live_chart/"


def _sources() -> dict[str, str]:
    if not _SRC.is_dir():
        raise FileNotFoundError(f"{_SRC} does not exist; retarget this guard")
    return {
        path.relative_to(_REPO_ROOT).as_posix(): path.read_text("utf-8")
        for path in sorted(_SRC.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _ui_sources() -> dict[str, str]:
    return {
        rel: text
        for rel, text in _sources().items()
        if is_ui(rel) and not rel.startswith(_LIVE_CHART_PACKAGE)
    }


def test_the_scan_has_a_subject() -> None:
    assert len(_ui_sources()) > 100


def test_the_live_chart_package_is_still_where_the_stream_is_started() -> None:
    wired = [
        rel
        for rel, text in _sources().items()
        if rel.startswith(_LIVE_CHART_PACKAGE) and "start_stream" in text
    ]
    assert wired, "the package that starts a candle stream moved: retarget the guard"


def test_the_charts_of_the_desk_the_market_and_the_bots_are_live_charts() -> None:
    classes = live_chart_classes(list(_sources().values()))

    assert {"LiveCandleChart", "DeskChart", "MarketChart", "BotChart"} <= classes


def test_no_ui_file_wires_a_live_price_into_a_chart_but_through_the_live_chart() -> (
    None
):
    live_charts = live_chart_classes(list(_sources().values()))
    found = {
        rel: hits
        for rel, text in _ui_sources().items()
        if (hits := wiring_violations(text, live_charts))
    }

    assert not found, (
        "build the chart on LiveCandleChart (src/support/charting/live_chart/) so it "
        "has the four states, the reason and the age:\n"
        + "\n".join(f"{rel}: {'; '.join(hits)}" for rel, hits in sorted(found.items()))
    )
