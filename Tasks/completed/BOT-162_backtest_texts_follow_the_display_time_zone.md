# BOT-162 — The Backtest mode's texts show times in the display time zone the person picked

**Status:** ✅ Done (2026-10-19)
**Priority:** P3
**Board:** The config diff's time range, the run-history label, the stale-metadata sentence, the coverage message and the imported-report banner wrote UTC while the trades table followed the chosen zone; each now writes in the chosen display time zone and names it unless it is UTC. A text is not rewritten when the zone changes.
**Source:** the review of PR #389 (`EPIC-033N`, finding 7), and the owner's go-ahead for this follow-up, 2026-10-06: "oki vụ muối giờ" (OK on the time-zone matter).
**Risk:** 🟢 — only the time zone of times written in texts changes; no figure, run or stored value does
**Complexity:** S — five call sites in `backtesting/ui`, one formatter that already takes a zone
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** `EPIC-033N` (PR #389), which moves these texts onto the formatter

---

## 1. Context and problem
The Backtest mode lets the person pick a display time zone (a view setting: data and runs stay UTC). The trades table and the chart's crosshair follow it. The trades table does this through `ZonedValueFormatter` (`src/support/ui_kit/value_formatter.py`), and the crosshair through `CrosshairController.set_display_timezone`.

After #389, the mode's other times are written by `write_value(ColumnKind.TIMESTAMP, …)`, which is always UTC:
- the run's event log (`logic/run_texts.py` `moment_text`);
- the run-history label (`logic/session_run_history.py`);
- the stale-metadata sentence in the config diff (`coordinators/strategy_config_coordinator.py`);
- the coverage message (`coordinators/data_sync_coordinator.py`);
- the imported-report banner (`logic/report_import.py`).

With a non-UTC zone chosen, the run history names one time and the trade log another for the same moment. This matches master: these texts were UTC before #389 as well. So this is not a regression, but it is an inconsistency a person can see.

## 2. Acceptance criteria
- [x] With a display time zone other than UTC chosen in the Backtest mode, every time the mode writes in a text (event log, run-history label, config diff, coverage message, imported-report banner) is in that zone, as the trades table is.
- [x] Changing the zone rewrites the texts that are still on screen (the history label, the banner), or the texts state the zone they are in. The choice between these is recorded in §3.
- [x] With UTC chosen, every text reads as it does today.

## 3. Design
**Decision (the task's first question): the texts state their zone; none is rewritten.** A text written in a non-UTC zone ends with the zone's name (`2026-01-01 22:20:05 Asia/Ho_Chi_Minh`), so it stays true after the person picks another zone, with no re-render path for a transient message (a coverage message, a diff) and no history to rewrite. In UTC every text reads exactly as before (the existing assertions are unchanged); the two sentences that already said "UTC" now say the zone. The zone named is the one the formatter really applied (`resolve_zone_info(...).key`), so an unresolvable setting is written, and named, as UTC rather than mislabelled (see `BUG-234` for the system zone).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/ui/logic/run_texts.py`, `session_run_history.py`, `report_import.py` | Write times with the mode's zone |
| `src/modules/backtesting/ui/coordinators/strategy_config_coordinator.py`, `data_sync_coordinator.py` | The same |
| `src/support/ui_kit/value_formatter.py` | Possibly a `write_value` variant that takes a zone |

## 5. Testing
- A unit test per text: a fixed UTC instant, written under a non-UTC zone, reads in that zone, and under UTC reads as today.
- ~~A presenter test: changing the zone rewrites the history label.~~ Replaced (§3 decision: texts name their zone and are not rewritten) by presenter tests that the screen hands each text the zone it holds now: the config diff, the no-data message and the history rows, plus a test that the sync worker's provider and the preview's coverage message read the same view model (`test_backtest_timezone_presenter.py`).

## Implementation notes (written when done)
The "event log" of the task is the config diff (`BacktestRunConfig.compute_diff_summary`, whose time range was the only time in it): it takes the zone and names it once for the range (`time_range_diff_text`). The other four sites take the zone from the screen's `time_range.displayTimezone` (the coverage message of the sync worker through a `time_zone` provider on `DataSyncCoordinator`, read as the trades table's formatter reads it). The writers are `moment_in_zone`, `zone_suffix` and `zoned_moment_text` in `logic/run_texts.py`, over `AppValueFormatter(zone)`; `BacktestRunSnapshot.label` became a method taking the zone, and the presenter's history rows are built by `run_history_rows`. `backtest_presenter.py` stays at its baseline and `backtest_fsm_matrix.py` shrank by four lines (its baseline entry is lowered). `DataSyncCoordinator` takes the zone provider as a required argument, so a forgotten wiring is a type error and not UTC. `BUG-234` (the "System" zone falls back to UTC) is not fixed here: the criteria are met for a named zone, and a System choice behaves as the trades table does.
