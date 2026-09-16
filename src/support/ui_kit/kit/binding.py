"""Two-way property binding for QtWidgets — the mechanism QML gave away for
free, rebuilt on the same Qt metaobject machinery QML itself uses.

BUG-064 — losing QML (`EPIC-006`) did not only cost a syntax. It replaced a
*declared relationship the framework keeps true* with *code somebody has to
remember to call at the right moment*, and every round of BUG-064 was one of
those moments nobody had remembered:

- the dialog only read its widgets when Save was clicked, so Enter and
  focus-loss silently discarded what the user typed;
- auto-commit was later wired by scanning `findChildren(QLineEdit)`, so spin
  boxes, check boxes and combos were silently dropped;
- the view only refreshed from the ViewModel inside an explicit
  `_sync_properties()` call, so between calls it could display a stale value
  with nobody noticing.

A binding has no such moments. `bind()` declares "this widget's value and
this QObject property are the same thing", and both directions are then kept
true by Qt signals — the ViewModel changing from anywhere (another screen, a
background job, a config reload) updates the widget, and the user editing the
widget updates the ViewModel.

Nothing here knows about any screen or domain concept; it needs only that the
source is a `QObject` whose property is writable and has a notify signal (Qt
Properties declared with `notify=` satisfy this, which `BackTestViewModel`'s
already do).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject

from .widget_value import (
    connect_value_committed,
    read_widget_value,
    write_widget_value,
)


class PropertyBinding(QObject):
    """Keeps one widget's value and one `QObject` property equal, both ways.

    @details Construction performs the initial sync (source -> widget), so a
    freshly bound widget always shows the current value rather than whatever
    it was built with.

    **Parented to the widget it binds**, which is why this is a `QObject` at
    all: a binding is nothing but signal connections held by this instance, so
    a plain object dropped by the caller would be garbage-collected and the
    binding would stop working — silently, with the widget still on screen
    looking fine. Qt's parent-child ownership makes the binding live exactly
    as long as the widget does, so `bind(...)` is safe to call without
    keeping the result. (Caught by this module's own tests, which first bound
    without holding a reference and saw both directions go dead.)

    The two directions would otherwise feed each other — writing the widget
    emits its committed signal, which would write the source, which emits its
    notify signal, which would write the widget again. `_syncing` breaks that:
    while one direction is running, the other stands down. It is not a
    "re-entrancy workaround" bolted on afterwards; a binding is by definition
    a cycle, and the guard is how the cycle is made to settle in one pass.
    """

    def __init__(
        self,
        widget: Any,
        source: QObject,
        property_name: str,
        coerce: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(widget)
        self._widget = widget
        self._source = source
        self._property_name = property_name
        self._coerce = coerce
        self._syncing = False

        meta_property = self._meta_property()
        if not meta_property.hasNotifySignal():
            raise ValueError(
                f"{type(source).__name__}.{property_name} has no notify signal, "
                "so a binding could never observe it changing"
            )
        if not meta_property.isWritable():
            raise ValueError(
                f"{type(source).__name__}.{property_name} is not writable, "
                "so a binding could never push an edit back into it"
            )

        self._pull_from_source()

        notify_name = meta_property.notifySignal().name().data().decode()
        getattr(source, notify_name).connect(self._pull_from_source)
        connect_value_committed(widget, self._push_to_source)

    def _meta_property(self) -> Any:
        meta_object = self._source.metaObject()
        index = meta_object.indexOfProperty(self._property_name)
        if index < 0:
            raise ValueError(
                f"{type(self._source).__name__} declares no Qt property "
                f"{self._property_name!r} — a plain Python attribute cannot be "
                "bound, since nothing announces when it changes"
            )
        return meta_object.property(index)

    def _pull_from_source(self) -> None:
        """Source -> widget. This is the direction manual code kept
        forgetting: it now happens whenever the source says it changed, not
        only when someone calls a sync method."""
        if self._syncing:
            return
        self._syncing = True
        try:
            write_widget_value(self._widget, self._source.property(self._property_name))
        finally:
            self._syncing = False

    def _push_to_source(self) -> None:
        """Widget -> source, on whatever counts as a commit for that widget
        kind (see `widget_value.connect_value_committed`)."""
        if self._syncing:
            return
        self._syncing = True
        try:
            value = read_widget_value(self._widget)
            if self._coerce is not None:
                try:
                    value = self._coerce(value)
                except (TypeError, ValueError):
                    # A half-typed value the widget's own validator allowed
                    # ("-", "1.") but the target type rejects. Leave the source
                    # untouched: the user is mid-edit, and the next commit will
                    # carry the finished value.
                    return
            self._source.setProperty(self._property_name, value)
        finally:
            self._syncing = False


class BindingGroup:
    """Every relationship one view declares, stated together in one block.

    Lifetime is NOT this class's job — each `PropertyBinding` is parented to
    its own widget and outlives this group regardless. What the group buys is
    readability (the whole set of bindings in one place, the way a QML file
    put them beside the widgets) and a count for tests to assert against.
    """

    def __init__(self) -> None:
        self._bindings: list[PropertyBinding] = []

    def bind(
        self,
        widget: Any,
        source: QObject,
        property_name: str,
        coerce: Callable[[Any], Any] | None = None,
    ) -> PropertyBinding:
        binding = PropertyBinding(widget, source, property_name, coerce)
        self._bindings.append(binding)
        return binding

    def __len__(self) -> int:
        return len(self._bindings)
