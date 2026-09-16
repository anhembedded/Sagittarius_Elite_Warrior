"""`InfoField` — one row of a chart's status panel.

HLD §3.4 lists this among `support/charting`'s published contracts, beside
`IChartHost`, `MarkerPoint` and `RegionSpan`, and its two consumers say why:
`chart_card` renders the panel, and the indicator-script runner fills it. It
describes the *shape of a row on a chart*, not a rule about indicators.

`EPIC-025` PR 1.6f moved it out of `domain/indicator_scripts/
base_indicator_script.py`, where it sat beside the script base class. That file
re-exports it, so every existing consumer keeps its import; the move exists so
`support/charting` can be extracted without importing the indicator tree, which
`support/* -> legacy` forbids outright.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InfoField:
    """
    @brief One row of a script's status panel (Pine's `table.cell`), e.g.
    ("Trend", "UP", color=green).
    @details Only ever shown for the most recently computed bar — a status
    panel reports "where things stand now", not a time series, so there is no
    history to keep. That also removes any need for Pine's `barstate.islast`
    guard: whichever bar was computed last is definitionally the one whose
    info is current.
    """

    label: str
    value: str
    color: str | None = None
