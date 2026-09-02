# qml/DataTable — the shared table skeleton, extracted from three copies

`BOT-124`. Before this existed, `src/presentation/ui/qml/` had three tables —
`TradeLogTable`, `KlineInspectorTable`, `DatabaseStatusTable` — each a
hand-rolled copy of the same shape: root `ColumnLayout` → header `RowLayout`
of `Text` cells bound to `readonly property int <x>ColumnWidth` → a divider
`Rectangle` → `ListView { clip; model; delegate }` → an empty-state `Text`.
Measured, not assumed: the three `.qml` files were 141/139/140 lines, and
their tails (`TradeLogTable.qml:111-141` vs. `KlineInspectorTable.qml:109-139`)
were near character-identical — only `objectName`, the delegate type, the
column-width property names, and the empty-state copy differed.

`EPIC-021I` needs two more tables (open positions, pending orders). Writing
them against the same hand-copied skeleton would have made them copies
four and five — `qml-rule.md` §0.2 names exactly this shape ("a
near-identical shape is the signal to generalise the existing component")
and gives a real precedent in this same repo for what that looks like:
`SelectListVM` absorbed `TimezonePickerVM` and the original was deleted,
not kept as a forwarder.

## What `DataTable` owns, and what it deliberately does not

Only the frame every table shared: the header row, the divider, the
`ListView`, the empty-state message. Three things stayed in each caller
on purpose (BOT-124 §5) — folding them in would trade three copies for one
component with three `if` branches, the same defect in different clothes:

- `TradeLogTable.qml` keeps its filter-tab row (`vm.filterTabs`).
- `KlineInspectorTable.qml` keeps its subtitle line
  (`symbol (interval) • N nến`).
- `DatabaseStatusTable.qml` keeps its search field (inside `kit/PanelHeader`)
  and its per-row action buttons (those live in `DatabaseStatusRow.qml`,
  untouched by this extraction).

## No Python ViewModel

`qml-rule.md` §1.3: a widget with nothing to derive — only properties a
caller sets directly — does not get a `_vm.py`. `DataTable`'s own
`columns`/`rowsModel`/`rowDelegate`/`isEmpty`/`emptyText` are plain
pass-throughs; nothing here computes, filters, or validates. Same
convention `qml/kit/`'s six components already use — `__init__.py` exists
only so `tests/` resolves to its own package path.

## Column widths stay one source of truth, just moved

`ui-presentation-rule.md` requires column widths to be declared once and
bound to both the header and every row delegate. Before this extraction
that "once" lived inside each table's own file (a `readonly property int`
read directly by both its header `Text` cells and its row delegate's
width properties). After extraction it is unchanged in spirit: each
caller still defines its own `readonly property int xColumnWidth`
constants, and passes the *same* values into both `DataTable`'s `columns`
array (`{ width: root.xColumnWidth }`) and its own `rowDelegate`'s width
properties. `DataTable` itself never invents a second source — it only
renders whatever `columns` says.

## Row delegate sizing: `ListView.view.width`, not an `id` reference

The three original tables sized their delegate with `width: rowsView.width`
— a direct reference to the `ListView`'s own `id`, valid because the
`ListView` and its `delegate:` assignment lived in the same file. Once the
`ListView` moves inside `DataTable.qml` and the delegate `Component` is
authored in the *caller's* file, that `id` is no longer in scope. The fix
is also the more idiomatic one: `width: ListView.view.width`, an attached
property Qt Quick gives every delegate instance regardless of which file
its `Component` body is written in, since the attachment happens at
instantiation time (when the `ListView` creates the delegate), not
lexically. `TradeLogRow`/`KlineInspectorRow`/`DatabaseStatusRow.qml`
themselves needed zero changes — only the three call sites that
instantiate them.

## What did not move

`TradeLogTable.qml`'s "RETURN" column stayed a bare literal `width: 70` in
both its `columns` entry and `TradeLogRow.qml`'s own delegate (pre-existing:
`TradeLogRow.qml:112` already hardcoded `70` rather than reading a shared
property, unlike every other column in that table). Not this task's job to
fix — BOT-124 is an extraction, not a behavior change, and the two `70`s
already had to agree with each other before this widget existed.

## Test coverage

`tests/test_data_table_qml.py` covers `DataTable` in isolation: an
0/N-column header, `fillWidth` vs. fixed-width columns, `isEmpty` toggling
the empty label, and that `reuseItems`/`rowSpacing` reach the internal
`ListView`. It does not re-test `TradeLogRow`/`KlineInspectorRow`/
`DatabaseStatusRow` — those already have their own coverage, unmoved and
unmodified by this extraction, and the same `tests/**` guard
(`test_qml_library_does_not_import_screens.py`) still applies.

## Measured, not asserted — 0 tests changed, real line reduction

Every existing test for the three migrated tables passes with **zero
asserts touched**: `TradeLogTable` 17/17, `KlineInspectorTable` 8/8,
`DatabaseStatusTable` 23/23 (including the `BUG-076` regression test,
which reads geometry inside `DatabaseStatusRow.qml`, never touched by this
extraction). `tests/unit/presentation/ui/qml/` (all guards, including
`test_qml_library_does_not_import_screens.py`) and
`tests/unit/presentation/ui/screens/` (819 tests, both real embedders)
stay green. A `git stash`-diffed `--collect-only` of the mandatory gate's
own test target (`Sagittarius_Elite_Warrior/tests`) shows **zero** added,
removed, or renamed test IDs — the only observed count delta (+5, in
`tests/unit/test_logging_namespace_guard.py`'s per-file parametrization)
is that guard picking up this widget's 5 new `.py` files, none of which
call `logging.getLogger()`.

`.qml` line count, the three wrapper files:

| File | Before | After |
| :--- | ---: | ---: |
| `TradeLogTable.qml` | 141 | 91 |
| `KlineInspectorTable.qml` | 139 | 74 |
| `DatabaseStatusTable.qml` | 140 | 88 |
| **3 wrappers, sum** | **420** | **253** |

`DataTable.qml` itself is 127 lines — even counted once against the total
(420 → 253 + 127 = 380), the net is smaller, and a sixth table costs close
to nothing: its own column list plus a row delegate, no new header/list/
empty-state code.
