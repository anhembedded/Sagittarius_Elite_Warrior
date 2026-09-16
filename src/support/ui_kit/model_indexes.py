"""`AnyIndex` — every Qt index type a model method may be handed.

PySide6 passes `QPersistentModelIndex` to `data()` on some call paths, so a
`QModelIndex`-only annotation is a lie the type checker cannot catch but Qt can
produce: mypy reports it as a Liskov violation against
`QAbstractItemModel.data`, which is exactly what it is.

**Why it lives here and not beside a model.** `EPIC-025` PR 1.6g moved the
indicator-script list model into `support/indicators/ui`, and the alias it
needed was already written — once — inside
`presentation/ui/components/order_book/table_models.py`. Reaching for it there
is `support -> legacy`, which the boundary rule refuses outright, and it stays
refused after that file becomes `modules/trading/ui`, because `support ->
modules` is refused too. A second copy of a four-line alias in each tree is the
duplication this epic exists to remove, so the alias moved to the one package
both trees may import whole.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex

type AnyIndex = QModelIndex | QPersistentModelIndex
