# EPIC-034I — Every chart that shows live market prices is built on the shared live chart

**Status:** ✅ Done (2026-10-07)
**Source:** the owner, 2026-10-07, approving it after `EPIC-034G` gave the Bots chart its four states: *"tui kỳ vọng là sau này dù chart nào cũng làm như vậy"* (I expect that from now on every chart behaves this way).
**Risk:** 🟢 — a test-side guard; no production code changes
**Complexity:** S — one scanner, one guard, probes, a registry row
**Epic:** [EPIC-034](../README.md)
**Depends on:** [EPIC-034G](EPIC-034G_chart_live_state.md) (the four-state `LiveCandleChart` it protects)

---

## 1. Context and problem
`EPIC-034G` made the shared `LiveCandleChart` (`src/support/charting/live_chart/`) carry the four states every live chart must show: History, Connecting, Live, Error, with the reason and the age of the last update. Today the Desk's chart (`DeskChart`), the Market mode's tabs (`MarketChart`) and the Bots mode's chart (`BotChart`) are all built on it, but nothing keeps the next chart from wiring a stream into a `ChartCard` by hand and saying nothing when the stream is gone — which is what the Bots chart did until `EPIC-034A`/`034G` (`bot_chart_host.py`, "Bots never connected `LiveCandleChart.logged`").

## 2. Acceptance criteria
- [x] An architecture guard fails when a UI file wires a live price into a chart other than through `LiveCandleChart`: pushing a candle into a `ChartCard` beside a live source (R1), building a `ChartCard` beside a live source with no `LiveCandleChart` (R2), or starting a candle stream itself (R4). — `test_every_live_chart_goes_through_the_live_chart.py`
- [x] Probe tests feed each rule a source it must catch and one it must let by, including a source named by shape that no list holds. — `test_live_chart_wiring_probes.py` (17 probes; the guard itself has 4 tests)
- [x] The guard has a `scanned_roots_registry` row. — `("tests/unit/architecture/test_every_live_chart_goes_through_the_live_chart.py", (("src", "*.py"),))`
- [x] Charts that never stream are let through by their shape, not by a name list: the Backtest and the Grid backtest charts read stored candles (`IHistoricalKlines`), the Desk equity chart pushes equity samples; none refers to a live source. — probes `test_a_chart_of_stored_candles_is_let_by_…`, `test_a_chart_of_equity_samples_is_let_by_…`; the guard holds no exemption.
- [x] The guard is shown to fail on the real tree. — see Implementation notes.

## 3. Design
A **live price source is a shape, not a list**: a name ending in `MarketStream`, `CandleFeed`, `TickFeed` or `TickEvent` (the market-data ports and events), or a raw socket module (`websockets`, `binance.ws`, `binance.streams`). `LiveCandleChart` and every class built on it are found by walking the subclasses of all of `src/`, so a new chart built on a chart built on it is compliant without being named. The one package that is the wiring, `support/charting/live_chart/`, is the scan's only exclusion. What it cannot see — a source reached under a name that matches none of the shapes, a chart handed candles by a caller that holds the source — is written in `live_chart_wiring.py`; the first is the pattern's reach, widened on the day a source is named otherwise, the second is that caller's file, scanned for the same source. Pattern over list: P5 (a vetted shape of this repository's own guards, `test_venues_are_shown_by_title.py`) and P1 (a mechanical barrier, not a reviewer's memory).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/live_chart_wiring.py` | the scanner: pure functions of one file's source |
| `tests/unit/architecture/test_every_live_chart_goes_through_the_live_chart.py` | the guard over `src/` UI files |
| `tests/unit/architecture/test_live_chart_wiring_probes.py` | what each rule catches and lets by |
| `tests/unit/architecture/scanned_roots_registry.py` | the guard's row |

## 5. Testing
Unit, architecture tier. A reviewer is required (a guard is a rule change, `.claude/skills/pr-review`).

## Implementation notes (written when done)
**Delivered** on branch `claude/epic-034-pr5-design-run-live-chart` (PR-5).

**On the real tree** the guard finds nothing to refuse: every chart that refers to a live source is a `LiveCandleChart` or built on one (`DeskChart`, `MarketChart`, `BotChart`; `test_the_charts_of_the_desk_the_market_and_the_bots_are_live_charts`), and no UI file calls `start_stream`. It is a guard against the next chart, and was proved to fail rather than assumed to: each mutation below was planted in the real tree, turned the guard red, and was removed.

| Planted in `src/` | Result |
| :--- | :--- |
| a UI file importing `IMarketStream` and building a `ChartCard(…)` | red, rule R2 |
| the Desk equity chart's file (`desk_equity.py`) also importing `MarketTickEvent` | red, rule R1 on its `append_closed_candle` |
| a UI file calling `feed.start_stream(…)` | red, rule R4 |
| `BotChart` no longer built on `LiveCandleChart` (`class BotChart(QObject)`) | red: rule R2 on `bot_chart_host.py` and `bots/ui/chart/preview.py`, the two files that build a `ChartCard` for it |

**Verification.** `tests/unit/architecture` green; commit tier PASS. The registry's own completeness guards (`test_every_path_scanning_test_is_registered`, `test_guard_scans_its_registered_root`) accept the new row.
