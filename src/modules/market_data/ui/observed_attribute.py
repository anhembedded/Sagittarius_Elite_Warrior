"""A view-model attribute that announces its own change.

`EPIC-033M` replaced the `QtCore.Property` triplet (`BUG-152`) with plain
Python. Six fields of `DataManagementViewModel` shared one behaviour: normalise
the incoming value, compare, assign, emit the field's change signal only on a
real change. This descriptor holds that behaviour once, so the view model
declares each field in one line and keeps its `<attr>Changed` signal names.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import overload


class ObservedAttribute[T]:
    """Stores the value in `self.<attr>` and emits `self.<signal>` on change.

    @param attr Instance attribute holding the value; set in `__init__` of the
    owner before the first read.
    @param signal Name of the owner's change signal, resolved on the instance.
    @param normalize Applied to an incoming value before the comparison.
    @param ignore_empty A falsy normalised value is a no-op: writing "" never
    clears a symbol, an interval or a format.
    """

    def __init__(
        self,
        attr: str,
        signal: str,
        normalize: Callable[[object], T] | None = None,
        *,
        ignore_empty: bool = False,
    ) -> None:
        self._attr = attr
        self._signal = signal
        self._normalize = normalize
        self._ignore_empty = ignore_empty

    @overload
    def __get__(self, owner: None, owner_type: type) -> ObservedAttribute[T]: ...

    @overload
    def __get__(self, owner: object, owner_type: type) -> T: ...

    def __get__(
        self, owner: object | None, owner_type: type
    ) -> ObservedAttribute[T] | T:
        if owner is None:
            return self
        return getattr(owner, self._attr)

    def __set__(self, owner: object, value: object) -> None:
        if self._normalize is not None:
            value = self._normalize(value)
        if self._ignore_empty and not value:
            return
        if value != getattr(owner, self._attr):
            setattr(owner, self._attr, value)
            getattr(owner, self._signal).emit()
