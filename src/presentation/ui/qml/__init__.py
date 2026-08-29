"""QML widgets, one directory per widget, each with its own ViewModel.

`EPIC-015`. Layout, per the user's constraint *"widget sẽ tạo riêng ở 1 DIR,
widget viewmodel sẽ được test riêng"*:

    qml/
      host.py                     QmlOverlay — widget chrome, QML body
      <Widget>/
        <Widget>.qml              layout and bindings only
        <widget>_vm.py            all state and rules — tested with no GUI
        NOTES.md                  why this widget exists

The split is load-bearing, not cosmetic. Everything that can be wrong lives
in the `.py`, where `mypy`, `ruff` and `pytest` can see it; the `.qml` holds
only what has to be declarative. A widget ViewModel is a plain `QObject` and
its tests construct **no `QApplication` at all** — measured, see the epic's
`spike/vm_alone.py`.
"""

__all__ = ["QmlOverlay"]


def __getattr__(name: str):
    """Load the legacy app host only when a caller explicitly asks for it.

    Standalone QML component sets live below this package and must not import
    the application's QmlOverlay/QtWidgets bridge merely because Python is
    discovering their colocated tests.
    """
    if name == "QmlOverlay":
        from .host import QmlOverlay

        return QmlOverlay
    raise AttributeError(name)
