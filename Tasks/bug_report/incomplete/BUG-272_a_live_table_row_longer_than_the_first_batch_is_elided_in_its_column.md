# BUG-272 — A live table's column is sized from its first rows only, so a later, longer row is cut off (the Developer event log's `Event` column, 151 px of 157)

- **Reported:** 2026-10-27 (coordinator: `master-warrior` red after the merge of #738, GitHub Actions run 40419536949, head `58aa56732`)
- **Severity:** 🟡 P2 — a long event name in the Developer mode is shown with an ellipsis, and the red `test_workbench_conformance` check blocks every pull request based on `master-warrior` (#739 waited on it).
- **Status:** Open
- **Board:** `SpecTable` relied on the Engine fitting a table's columns once, when its first rows arrive; the Developer event log is fed by the bus after that, so an event named longer than the first drain stayed elided and the conformance check failed or passed with the boot's timing.
- **Context:** the Developer mode → `src/shell/developer_mode/` (`EventLogTableModel`, `DeveloperView.append_events`) → the shared `SpecTable` in `src/support/ui_kit/spec_table.py`
- **Environment:** GitHub Actions `gate (Rest)`, Linux, offscreen; at 1024x700, 1366x768 and 1920x1080. Reproduced as a unit test, not as the CI timing.

## Reproduction
Append one short event to a shown `DeveloperView`, then a batch holding a longer event name; the `Event` column keeps the width of the first batch. In CI the same happens at boot: which names are in the first drain decides the width. The same test passed on `18eca1c0`, `1cffd330` and once on a re-run of #738's head, so it depends on timing, not on a font or a screen size (it failed at all three sizes).

## Symptom
```
FAILED .../test_workbench_conformance.py::test_workbench_conformance[True-1366x768] - AssertionError: developer@1366x768/columns_shown_whole: QTableView 'tblEventLog': column 'Event' is 151 px, its content 157 px
```
(also `1024x700` and `1920x1080`). Expected: every column shows its cells whole (`ui-presentation-rule.md` §9).

## Root cause
The Engine's `configure_item_view._FirstRowsFitter.on_rows_inserted` fits the columns only when the insert fills an empty model (`rowCount == last - first + 1`) and never again until a reset (Engine `configure_item_view.py`, the pin of `engine.ref`). The columns are `Interactive`, so nothing widens them later. `DeveloperView.append_events` (`developer_view.py:89` at `58aa567`) appends the bus's events with `beginInsertRows`, never a reset, so the width is whatever the first drain held; a longer name arriving later is elided. Which names the first drain holds depends on how many boot events were published before the first 250 ms drain, which 047B's host-facts work changed. The conformance check (`workbench_text_checks.py:62`) compares the section with `sizeHintForColumn` of the rows shown. The same shape exists wherever a `SpecTable` is fed by inserts: `DatabaseStatusTableModel.upsert_row` (`database_status_table_model.py:195`).

## Fix
`SpecTable` (the one place every table is built) grows a column to its content on every `rowsInserted` of its proxy, only ever wider, so a width the person narrowed stays until a row needs more. The Engine is untouched; the columns stay `Interactive`.

## Regression test
`tests/unit/shell/developer_mode/test_developer_mode.py::test_a_name_longer_than_the_first_batch_still_shows_whole` — red before (`assert 60 >= 256`: the column stayed at the minimum, the content needed 256 px); green after.

## Verification
Test red before and green after at `58aa567`, locally (offscreen). `tests/unit/shell/developer_mode` and `tests/unit/support/ui_kit` pass. The CI failure itself was not reproduced locally (the boot's drain timing differs): the full conformance run here is identical with and without the fix (one font-dependent failure, `backtest@1024x700/fits_the_window`, in both). The gate is the pull request's `ci-local.ps1 -Full` run.

## Suggested next steps
Move the grow-only fit into the Engine's fitter, in its own Engine pull request, if the owner wants it there.
