# EPIC-033J — Data mode: keep history complete, laid out as HLD §11.2.1 designs it

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟡 — destructive commands
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** [SPEC-001](../../../../Docs/SPEC/SPEC-001_sync_a_symbols_history.md); SPEC-008 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Data Management is a page of metric cards, a header with Vacuum and Purge, and a column of full-width 40 px buttons, the fifth hidden by its own scroll area.

## 2. Acceptance criteria
- [x] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it).
- [x] Data menu: Sync…, Scan, Repair Gap…, Compact Database, Delete Data…; the table's context menu repeats the per-row commands; Delete Data… confirms with a safe default. (Named as HLD §11.2.3's table now lists them; see the notes.)
- [x] Record count and database size show in the status bar.
- [x] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [x] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Data Management screen.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
- **The layout.** The view (`data_management_view.py`, rewritten) is a `WorkbenchSurface` on the `data_management` surface, which now accepts `WORKSPACE` and `CONSOLE`:
  - **Central:** the coverage table (`DatabaseStatusPanel`).
  - **Bottom:** the Gaps panel (`gaps_panel.py`), beside the window's Output pane, which shows the mode's `Sync` channel.
- **"Coverage table (symbol × timeframe)" is one row per shard.** A shard is a symbol at a timeframe, and each row carries its first and last candle, count and health. A matrix with symbols down and timeframes across would show one figure per cell and lose the rest. It would also hold mostly empty cells, because a store holds a handful of timeframes per symbol.
- **Commands act on the selection.** Selecting a shard sets the view model's symbol and timeframe, which the scan, delete and export coordinators already read. The view's `DataSelection` tells the binding (`data_command_binding.py`) what is selected:
  - Check gaps, Inspect candles, Scan status, Export and Delete data wait for a selected shard. Check gaps waits for one with gaps.
  - Repair gap waits for a gap selected in the Gaps panel; Repair all gaps waits for any gaps listed.
  - Everything but Stop is disabled while a task runs, and Stop only then.
  - The table's context menu repeats Check gaps, Inspect candles and Delete data.
- **Questions are dialogs.**
  - Sync history… asks for the shard and an optional UTC range (`shard_dialogs.py`) and opens on the selected shard.
  - Import data… asks which shard the file belongs to, then for the file.
  - Export's format is the save dialog's file-type list, opening on the last format used.
  - These replace the rail's symbol and timeframe pickers, its date-range card and the format combo box.
- **Names follow HLD §11.2.3's table, which is the one list.** The table now lists every Data command. The task's own names (Sync…, Scan, Repair Gap…, Compact Database, Delete Data…) predate it and map as follows:
  - Sync… → Sync history…
  - Scan → Scan status / Scan all shards
  - Repair Gap… → Repair gap. It takes no "…" because it asks nothing.
  - Compact Database → Optimize database
  - Delete Data… → Delete data. It only confirms, so it takes no "…" (`ui-presentation-rule.md` §4, as Bots' Delete bot). Its question names the shard and keeps Cancel as the default.
- **The status bar.** The view offers words through `IStatusSource` (`EPIC-033H`'s seam): `Records: …`, `Database: …`, and, while a task runs, its text and a `QProgressBar`. The progress banner and its Cancel button are gone; Data → Stop stops the task.
- **The Gaps panel.** It replaces `GapInspectorDialog`, a modal overlay of hand-styled rows with a Repair button each. The gaps are now a table from its specs plus a one-line summary. The coverage bar is not rebuilt; the summary states the percentage.
- **Deleted:** `gap_inspector_dialog.py`, `time_range_card.py`, `field_style.py`, the Storage Vault header, the stat tiles and the rail, and the tests that drove them (`test_gap_inspector_widget.py`, `test_data_management_view_pickers.py`, `test_data_management_time_range_picker.py`).
  - The mypy exclude of `gap_inspector_dialog.py` was removed from `pyproject.toml` with the user's approval (2026-10-05).
- **Ratchets lowered to measured values:**
  - `baseline_app_styling.json`: `apply_role` calls 37 → 32 (files 19 → 17); `setStyleSheet` calls 113 → 89 (files 20 → 17); palette files 26 → 22.
  - Stock-controls entries for the three files are removed.
  - God files: the view leaves the list, and the presenter goes 631 → 620.
  - UI duplication 61 → 60.
  - Conformance: the `data_management` baseline row is removed.
  - The mode bar says "Data", as HLD §11.2.1 names the mode.
- **Review of PR #354 (two blocking findings, both fixed):**
  - **The selected shard had two owners.** Selecting a row wrote the view model's symbol and timeframe, and Sync history… and Import data… wrote them too. So after a dialog answered another shard and was cancelled, Delete data deleted that other shard while the table still showed the first selected.
    - Now `DataSelection` is the one source. Scan status, Export and Delete data read it and write the coordinators' fields only as they act.
    - Delete data asks the coverage table's own question, which names the shard and its candles, instead of a declared confirmation that could only say "the selected symbol".
    - Regression test: `test_a_dialog_never_moves_what_a_shard_command_acts_on`.
  - **Stop was enabled during CLEARING.** Delete, purge, import and export run as CLEARING, which has no cancel path, so a Stop there only orphaned the delete's completion. Stop now applies to SCANNING and SYNCING. Regression test: `test_stop_is_off_while_the_task_cannot_be_stopped`.
  - **Answered:** after a repair, the gap coordinator re-runs Check gaps for the shard, so the Gaps panel shows the post-repair report.
- **Still open, recorded rather than built:**
  - §5's Desktop E2E (open, use, rearrange, restart on a real display).
  - SPEC-008 is still unwritten (`Docs/SPEC/README.md` lists it as planned).
  - The symbol picker's favourites and recents are not offered in the Sync history… dialog; the editable combo box lists the symbol catalogue.
  - The view keeps its mypy exclude: it reads the view model's `Property` values, the debt `EPIC-002D` owns.
