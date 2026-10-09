"""`EPIC-028A` — a `cached_property` that builds under its instance's lock."""

from __future__ import annotations

from functools import cached_property
from typing import Any, Self, overload


class LockedCachedProperty[T](cached_property[T]):
    """`cached_property` that builds under the instance's `_lock`.

    @details Python 3.12 removed `cached_property`'s own lock, so two threads
    asking for an unbuilt part could each build one — a second metadata cache,
    or a second user data stream on one account (`EPIC-028A` review F1). The
    instance lock is re-entrant because a part builds the parts it depends on.
    """

    @overload
    def __get__(self, instance: None, owner: type[Any] | None = None) -> Self: ...
    @overload
    def __get__(self, instance: object, owner: type[Any] | None = None) -> T: ...
    def __get__(self, instance: object | None, owner: type[Any] | None = None) -> Any:
        if instance is None:
            return self
        with instance._lock:  # type: ignore[attr-defined]
            return super().__get__(instance, owner)
