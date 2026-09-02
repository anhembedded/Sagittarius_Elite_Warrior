"""Shared `qml/` table skeleton: header row, row `ListView`, empty state.

Pure QML — no Python ViewModel exists for it (qml-rule.md §1.3: a
component with nothing to derive, only properties a caller sets, does not
get one). `columns`/`rowsModel`/`rowDelegate`/`isEmpty`/`emptyText` are all
plain pass-through properties the caller sets directly; `DataTable` never
transforms or validates them. This file exists only so `tests/` resolves
to a unique package path (EPIC-015 §1 — one widget, one directory), same
convention as `qml/kit/__init__.py`.

Extracted (`BOT-124`) from three near-identical copies of this same
skeleton — `TradeLogTable`, `KlineInspectorTable`, `DatabaseStatusTable` —
see `NOTES.md` for the measurements that motivated it and what stayed
behind in each of the three.
"""
