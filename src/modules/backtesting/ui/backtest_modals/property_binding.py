"""Keeps one control and one view-model attribute equal, both ways.

`bind()` declares "this control's value and `source.<attribute>` are the same
thing", and both directions are then kept true by signals: the view model
changing from anywhere (another screen, a config reload) updates the control,
and the person editing the control updates the view model (`BUG-064`: a dialog
that reads its controls only at Save, or refreshes only inside an explicit
sync call, shows a stale value nobody notices).

The source is any object with a plain Python attribute and setter and a
`<attribute>Changed` signal, which is how every view model of this module
announces a change. A binding is a cycle (writing the control commits, which
writes the source, which announces, which writes the control); `_syncing`
lets the cycle settle in one pass.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QWidget

from .widget_values import (
    connect_value_committed,
    read_widget_value,
    write_widget_value,
)


class PropertyBinding:
    """One control bound to one attribute of a view model."""

    def __init__(
        self,
        widget: QWidget,
        source: object,
        attribute: str,
        coerce: Callable[[Any], Any] | None = None,
    ) -> None:
        self._widget = widget
        self._source = source
        self._attribute = attribute
        self._coerce = coerce
        self._syncing = False

        changed = getattr(source, f"{attribute}Changed", None)
        if changed is None:
            raise ValueError(
                f"{type(source).__name__} has no {attribute}Changed signal, so a "
                "binding could never observe it changing"
            )
        self._pull_from_source()

        # Closures, not bound methods: PySide holds a bound method of a plain
        # object weakly, so a binding nobody kept would go dead silently,
        # whereas a closure lives as long as the signal's sender does.
        def pull() -> None:
            self._pull_from_source()

        def push() -> None:
            self._push_to_source()

        changed.connect(pull)
        connect_value_committed(widget, push)

    def _pull_from_source(self) -> None:
        """Source -> control."""
        if self._syncing:
            return
        self._syncing = True
        try:
            write_widget_value(self._widget, getattr(self._source, self._attribute))
        finally:
            self._syncing = False

    def _push_to_source(self) -> None:
        """Control -> source, on whatever counts as a commit for that control."""
        if self._syncing:
            return
        self._syncing = True
        try:
            value = read_widget_value(self._widget)
            if self._coerce is not None:
                try:
                    value = self._coerce(value)
                except (TypeError, ValueError):
                    # A half-typed value the control allowed ("-", "1.") but
                    # the target type rejects: the person is mid-edit and the
                    # next commit carries the finished value.
                    return
            setattr(self._source, self._attribute, value)
        finally:
            self._syncing = False


class BindingGroup:
    """Every binding one dialog declares, held together for as long as it
    lives (a binding is signal connections only, so dropping it would not
    disconnect them, but holding them keeps the set countable)."""

    def __init__(self) -> None:
        self._bindings: list[PropertyBinding] = []

    def bind(
        self,
        widget: QWidget,
        source: object,
        attribute: str,
        coerce: Callable[[Any], Any] | None = None,
    ) -> PropertyBinding:
        binding = PropertyBinding(widget, source, attribute, coerce)
        self._bindings.append(binding)
        return binding

    def __len__(self) -> int:
        return len(self._bindings)
