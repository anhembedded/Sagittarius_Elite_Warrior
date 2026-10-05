# BOT-151 — Grouped trees are built from column specs like every flat table

**Status:** 🔵 Backlog
**Source:** the review of PR #351 (EPIC-033 P4d), 2026-10-05 — "the grouped-tree deferral names no owner"; this task is that owner.
**Risk:** 🟡 — four dialogs change how their rows are built
**Complexity:** M — an Engine mechanism, then four consumers
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md) (the open criterion 1 of `EPIC-033N`)
**Depends on:** an Engine change (separate repository, its own confirmation and PR)

---

## 1. Context and problem
`EPIC-033N` built every flat table through the Engine's `configure_item_view`. Four views are grouped trees, headings with rows under them, and still configure themselves: `metrics_detail_dialog.py`, `out_of_sample_comparison_dialog.py`, `report_comparison_dialog.py` (backtesting) and `timeframe_picker/dialog.py` (13 `item_view_config` calls in `baseline_stock_controls.json`). Each is a `QTreeWidget`, which forbids `setModel`; `configure_item_view` replaces the view's model and turns sorting on, which would scatter the groups. Their values are also written by hand, not by `AppValueFormatter`.

## 2. Acceptance criteria
- [ ] The Engine offers a grouped-tree configuration: column specs, a group per heading, whole-row selection, no editing, sorting within a group or none, and the kind delegate.
- [ ] The four dialogs are a `QTreeView` on a model built through it; their values go through `AppValueFormatter`.
- [ ] Their `item_view_config` entries leave `baseline_stock_controls.json`; `EPIC-033N` criterion 1 is ticked.

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
Not started.
