"""Shared QML primitives: PanelHeader, Button, LogPanel, DialogShell.

Pure QML — no Python ViewModel exists for any of these (qml-rule.md §1.3:
a component with nothing to derive, just properties a caller sets, does
not get one). This file exists only so `tests/` resolves to a unique
package path (EPIC-015 §1 — one widget, one directory).

Two exceptions: `progress_banner_widget.py`'s `ProgressBannerWidget` and
`status_pill_widget.py`'s `StatusPillWidget` are thin `QQuickWidget`
*hosts*, not ViewModels — each exists because its `.qml` is embedded
inline (no modal, no `QmlOverlay`) into a screen's own layout
(`DataManagementView` and `DevBoardPanel` respectively), and an inline
embed needs a Python object to occupy that layout slot. See `NOTES.md`'s
own section on each.
"""
