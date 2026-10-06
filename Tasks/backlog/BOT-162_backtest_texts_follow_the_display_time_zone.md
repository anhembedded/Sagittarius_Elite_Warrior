# BOT-162 — The Backtest mode's texts show times in the display time zone the person picked

**Status:** 🔵 Backlog
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
- [ ] With a display time zone other than UTC chosen in the Backtest mode, every time the mode writes in a text (event log, run-history label, config diff, coverage message, imported-report banner) is in that zone, as the trades table is.
- [ ] Changing the zone rewrites the texts that are still on screen (the history label, the banner), or the texts state the zone they are in. The choice between these is recorded in §3.
- [ ] With UTC chosen, every text reads as it does today.

## 3. Design
Not started. `ZonedValueFormatter` is the precedent: it asks the screen's zone each time it writes. A text writer can take the same zone provider instead of calling `write_value`. Whether the event log's past lines are rewritten on a zone change, or are left in the zone they were written in, is this task's first decision.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/ui/logic/run_texts.py`, `session_run_history.py`, `report_import.py` | Write times with the mode's zone |
| `src/modules/backtesting/ui/coordinators/strategy_config_coordinator.py`, `data_sync_coordinator.py` | The same |
| `src/support/ui_kit/value_formatter.py` | Possibly a `write_value` variant that takes a zone |

## 5. Testing
- A unit test per text: a fixed UTC instant, written under a non-UTC zone, reads in that zone, and under UTC reads as today.
- A presenter test: changing the zone rewrites the history label.
