# BOT-151 — Grouped trees are built from column specs like every flat table

**Status:** ✅ Done (2026-10-06)
**Source:** the review of PR #351 (EPIC-033 P4d), 2026-10-05 — "the grouped-tree deferral names no owner"; this task is that owner.
**Risk:** 🟡 — four dialogs change how their rows are built
**Complexity:** M — an Engine mechanism, then four consumers
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md) (the open criterion 1 of `EPIC-033N`)
**Depends on:** an Engine change (separate repository, its own confirmation and PR)

---

## 1. Context and problem
`EPIC-033N` built every flat table through the Engine's `configure_item_view`. Four views are grouped trees, headings with rows under them, and still configure themselves: `metrics_detail_dialog.py`, `out_of_sample_comparison_dialog.py`, `report_comparison_dialog.py` (backtesting) and `timeframe_picker/dialog.py` (13 `item_view_config` calls in `baseline_stock_controls.json`). Each is a `QTreeWidget`, which forbids `setModel`; `configure_item_view` replaces the view's model and turns sorting on, which would scatter the groups. Their values are also written by hand, not by `AppValueFormatter`.

## 2. Acceptance criteria
- [x] The Engine offers a grouped-tree configuration: column specs, a group per heading, whole-row selection, no editing, sorting within a group or none, and the kind delegate.
- [x] The four dialogs are built from column specs; their values go through `AppValueFormatter`. — As built: the timeframe picker is a `QTreeWidget` configured in place by the Engine; the three Backtest read-outs had already become flat `SpecTable`s in `EPIC-033L` (see the notes).
- [x] Their `item_view_config` entries leave `baseline_stock_controls.json`; `EPIC-033N` criterion 1 is ticked.

## 3. Design
Qt's own model/view: a `QStandardItemModel` (or a small tree model) with a heading item per group, shown in a `QTreeView` configured once by the Engine (P5). The timeframe picker's pin check box is a checkable item, not a widget.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| Engine `workbench/` | The grouped-tree configuration and its tests |
| The four dialogs above | Built from it |
| `tests/unit/architecture/baseline_stock_controls.json` | Lowered |

## 5. Testing
Engine: unit tests per behaviour. App: each dialog's existing tests, plus a test that a group's rows stay under their heading after a header click.

## Implementation notes (written when done)
- **Engine (PR #230, `engine.ref` 5a11c02).** `configure_item_view(tree, None, specs)` configures a `QTreeWidget` in place: it writes the header from the specs and applies the kind delegate, whole-row selection, no editing, sorting and column fitting; `SpecTreeItem` is a row that sorts on its raw `DisplayRole` value. Qt sorts each heading's children among themselves, so a group's rows stay under it. The design changed from §3's `QTreeView` on a model: a `QTreeWidget` keeps its items, so the timeframe picker's pin check boxes and in-place updates (`_render`, which must not rebuild during an `itemChanged`) stay as they were.
- **Timeframe picker.** `timeframe_picker/dialog.py` declares `COLUMNS` and is configured by the Engine with `APP_VALUE_FORMATTER`; its three `setSectionResizeMode` calls are gone, and `item_view_config` in `baseline_stock_controls.json` falls from 3 to 0 (no file left). Proof: `test_the_tree_is_configured_from_its_column_specs` and `test_sorting_orders_each_groups_rows_and_keeps_them_under_it` (`test_dialog_and_timeframe_actions.py`), red on the previous dialog (unconfigured; sorting off).
- **Its rows are `SpecTreeItem`s; its headings stay plain `QTreeWidgetItem`s.** In Engine 6c6eab6 a `SpecTreeItem` comparing two texts called `QTreeWidgetItem.__lt__`, which PySide dispatched back to the Python override: a recursion that ended in a segmentation fault on the first header click (measured with the sorting test above). The Engine fixed it in 5a11c02 (text compares directly, with a regression test), and the rows became `SpecTreeItem`s in the same app PR.
- **The three Backtest read-outs were not trees any more.** `EPIC-033L` (PR #365) had already rebuilt Metrics Detail, the out-of-sample comparison and the report comparison as `SpecTable`s from column specs, with the section as the first column; they have no `item_view_config` row. Their values arrive as formatted text in mixed units and sort back to the read-out's own order through `SORT_ROLE` (`readout_table.py`); a grouped tree would sort them on that text, so they stay flat tables.

