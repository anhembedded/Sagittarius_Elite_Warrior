"""Shared QML primitives: PanelHeader, Button, LogPanel, DialogShell.

Pure QML — no Python ViewModel exists for any of these (qml-rule.md §1.3:
a component with nothing to derive, just properties a caller sets, does
not get one). This file exists only so `tests/` resolves to a unique
package path (EPIC-015 §1 — one widget, one directory).
"""
