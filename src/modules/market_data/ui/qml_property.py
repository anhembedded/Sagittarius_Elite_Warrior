"""`EPIC-019C` — factory for the getter/setter/`Property()` triplet every
QML-facing `BaseQmlViewModel` subclass repeats by hand for each read-write
property: 133 `_get_*`/`_set_*` methods across the 4 ViewModels in
`presentation/ui/screens/`, none of which do more than "compare, assign,
emit only on a real change" — `BaseQmlViewModel` (engine) has no factory
for this, and stays that way here: the two repos are independent
(`CLAUDE.md`), so this lives in the app instead of the engine.

Trialled on `DataManagementViewModel` only (`EPIC-019C`) — not rolled out
to the other three ViewModels in this pass. Whether it's worth repeating
elsewhere is a decision for whoever does that next audit pass, once this
one has been live long enough to judge.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, Signal


def notifying_property(
    attr: str,
    prop_type: type,
    signal: Signal,
    normalize: Callable[[Any], Any] | None = None,
) -> Property:
    """Builds a QML-bindable `Property` backed by `self.<attr>`, emitting
    `signal` only when the value actually changes.

    @param attr Instance attribute holding the value, e.g. `"_selected_symbol"`
    — must already be set in `__init__` before QML can read the property.
    @param prop_type Qt property type — a Python type (`str`, `int`,
    `bool`, ...), passed straight through to `Property()`. No trialled
    property here needs a Qt type string (`"QStringList"`); widen this to
    `type | str` if one ever does, rather than fighting `Property()`'s stub
    with an ignore for a case that doesn't exist yet.
    @param signal The class-level `Signal()` this property notifies on —
    also becomes `Property()`'s own `notify=` signal, so each property's
    change signal is named in exactly one place.
    @param normalize Optional callable applied to an incoming value before
    the change check; a falsy normalized result is silently ignored — this
    matches the pre-existing convention that writing an empty string never
    clears a symbol or interval, it's a no-op. Leave `None` for a property
    that accepts any value, including a falsy one, as a real assignment.
    """

    def getter(self) -> Any:
        return getattr(self, attr)

    def setter(self, value: Any) -> None:
        if normalize is not None:
            value = normalize(value)
            if not value:
                return
        if value != getattr(self, attr):
            setattr(self, attr, value)
            # `Signal` is a descriptor; `__get__` binds it to `self` so it
            # can be emitted — the class-level object handed in as `signal`
            # can't be emitted directly, only an instance-bound one can.
            signal.__get__(self, type(self)).emit()

    return Property(prop_type, getter, setter, notify=signal)
