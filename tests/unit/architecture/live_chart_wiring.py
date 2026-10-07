"""What `test_every_live_chart_goes_through_the_live_chart.py` looks for, as pure
functions of one file's source, so the probes can feed them any shape.

**The rule (`EPIC-034I`, the owner's expectation: whatever chart shows live
market prices behaves the same way).** A chart that shows live prices is built
on `LiveCandleChart` (`support/charting/live_chart/`): it owns the four states
(History, Connecting, Live, Error), the reason and the age. So UI code does
not wire a market stream or a candle feed into a chart itself. Three shapes:

  · **R1, pushing.** A file that pushes a candle into a chart
    (`update_last_candle`, `append_closed_candle`, `update_last_volume`,
    `append_closed_volume`) and refers to a live price source.
  · **R2, building.** A file that constructs a `ChartCard` and refers to a live
    price source without referring to any `LiveCandleChart` (itself or a class
    built on it, found by walking the subclasses, never named here).
  · **R4, starting a stream.** A file that calls `start_stream`, the candle
    feed's live API, which only `LiveChartCoordinator` may.

**A live price source is a shape, not a list**: a name ending in `MarketStream`,
`CandleFeed`, `TickFeed` or `TickEvent` (the market-data ports and events), or
a raw socket (`websockets`, `binance.ws`, `binance.streams`). A chart that
never streams is let through by what it does not refer to: the backtest's
charts read stored candles (`IHistoricalKlines`), and the Desk's equity chart
pushes equity samples. Neither refers to a live source, so no name excuses
either.

What it cannot see: a source reached under a name that matches none of these,
and a chart handed candles by a caller that holds the source. The first is the
pattern's reach, widened on the day a source is named otherwise; the second is
the caller's file, which is scanned for the same source.
"""

from __future__ import annotations

import ast
import re

#: The candle push of `ChartCard`.
PUSH_METHODS = frozenset(
    {
        "update_last_candle",
        "append_closed_candle",
        "update_last_volume",
        "append_closed_volume",
    }
)
#: `ICandleFeed`'s live API.
STREAM_START_METHODS = frozenset({"start_stream"})
LIVE_SOURCE_NAME = re.compile(r"(MarketStream|CandleFeed|TickFeed|TickEvent)$")
RAW_STREAM_MODULES = ("websockets", "websocket", "binance.ws", "binance.streams")
LIVE_CHART_BASE = "LiveCandleChart"
CHART_CARD = "ChartCard"


def referred_names(tree: ast.AST) -> set[str]:
    """Every name a file imports or reads: imported aliases, bare names and
    attributes."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom | ast.Import):
            names.update(
                (alias.asname or alias.name).split(".")[-1] for alias in node.names
            )
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def live_sources(tree: ast.AST) -> list[str]:
    """The live price sources a file refers to, sorted."""
    found = {name for name in referred_names(tree) if LIVE_SOURCE_NAME.search(name)}
    for module in _imported_modules(tree):
        if any(
            module == raw or module.startswith(f"{raw}.") for raw in RAW_STREAM_MODULES
        ):
            found.add(module)
    return sorted(found)


def _method_calls(tree: ast.AST, methods: frozenset[str]) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in methods
    ]


def _builds_chart_card(tree: ast.AST) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == CHART_CARD)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == CHART_CARD)
        )
    ]


def live_chart_classes(sources: list[str]) -> set[str]:
    """`LiveCandleChart` and every class built on it, however deep, found by
    walking the bases of every class in `sources`."""
    bases_of: dict[str, set[str]] = {}
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ClassDef):
                bases_of.setdefault(node.name, set()).update(
                    base.id if isinstance(base, ast.Name) else base.attr
                    for base in node.bases
                    if isinstance(base, ast.Name | ast.Attribute)
                )
    found = {LIVE_CHART_BASE}
    grew = True
    while grew:
        grew = False
        for name, bases in bases_of.items():
            if name not in found and bases & found:
                found.add(name)
                grew = True
    return found


def wiring_violations(source: str, live_charts: set[str]) -> list[str]:
    """Each way `source` wires a live price into a chart outside
    `LiveCandleChart`, one sentence each."""
    tree = ast.parse(source)
    sources = live_sources(tree)
    found: list[str] = []
    for line in _method_calls(tree, STREAM_START_METHODS):
        found.append(
            f"line {line}: starts a candle stream itself (R4); only "
            "LiveChartCoordinator does"
        )
    if sources:
        for line in _method_calls(tree, PUSH_METHODS):
            found.append(
                f"line {line}: pushes a candle into a chart while referring to "
                f"{', '.join(sources)} (R1)"
            )
        if not referred_names(tree) & live_charts:
            for line in _builds_chart_card(tree):
                found.append(
                    f"line {line}: builds a ChartCard beside {', '.join(sources)} "
                    "with no LiveCandleChart (R2)"
                )
    return found
