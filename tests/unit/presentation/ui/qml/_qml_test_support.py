"""Shared support for tests that reach into a rendered QML scene.

Not app code — a test-only workaround for a real Qt gap `EPIC-015`'s pilot
found: `findChild(QObject, objectName)` does not reach items a `Repeater`
creates (they get the `Repeater`'s parent as their *visual* parent, not
their `QObject` parent, so `findChild`'s recursion never sees them), while
`childItems()` does. Kept once here rather than reimplemented per test file,
which is how the finding first got made twice while writing the bậc 2 pilot.
"""

from __future__ import annotations

from PySide6.QtQuick import QQuickItem


def named_descendants(root: QQuickItem) -> list[QQuickItem]:
    """Every item under `root` that has an `objectName`, in tree order.

    @details Always re-call this after any signal that can trigger a
    `Repeater` model rebuild (`rowsChanged`/`optionsChanged`/`cardsChanged`)
    rather than reusing items from a previous call — a `QVariantList` model
    rebuilds its delegates wholesale on every change (measured: the Python
    id of a `CheckBox` before and after a `rowsChanged` differ), so an item
    held across a refresh is a reference to a destroyed `QQuickItem`.
    """
    found: list[QQuickItem] = []
    for child in root.childItems():
        if child.objectName():
            found.append(child)
        found.extend(named_descendants(child))
    return found


def find_named(root: QQuickItem, object_name: str) -> QQuickItem | None:
    """The first descendant of `root` whose `objectName()` matches, or `None`."""
    for item in named_descendants(root):
        if item.objectName() == object_name:
            return item
    return None


def find_all_named(root: QQuickItem, prefix: str) -> list[QQuickItem]:
    """Every descendant of `root` whose `objectName()` starts with `prefix`,
    in tree order — for a `Repeater`'s rows, which all share one prefix."""
    return [
        item for item in named_descendants(root) if item.objectName().startswith(prefix)
    ]


__all__ = ["find_all_named", "find_named", "named_descendants"]
