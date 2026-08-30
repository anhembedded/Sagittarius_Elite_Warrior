"""Shared QML primitives: PanelHeader, Button, LogPanel, DialogShell.

Pure QML — no Python ViewModel exists for any of these (qml-rule.md §1.3:
a component with nothing to derive, just properties a caller sets, does
not get one). This file exists only so `tests/` resolves to a unique
package path (EPIC-015 §1 — one widget, one directory).

One exception: `progress_banner_widget.py`'s `ProgressBannerWidget` is a
thin `QQuickWidget` *host*, not a ViewModel — it exists because
`ProgressBanner.qml` is embedded inline (no modal, no `QmlOverlay`) into
`DataManagementView`'s own layout, and an inline embed needs a Python
object to occupy that layout slot. See `NOTES.md`'s own section on it.
"""
