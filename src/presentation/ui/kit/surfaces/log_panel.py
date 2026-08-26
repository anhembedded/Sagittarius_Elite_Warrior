"""
@brief `LogPanel` — a `Card` wrapping a scrolling log view with a live entry
count and Copy/Clear actions.
"""

from __future__ import annotations

import contextlib
from typing import Protocol

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QAbstractItemView, QListView, QWidget

from ..controls import Badge, StyledButton
from ..style import StyleRole, apply_role
from ..surface import Card

#: Fallback action labels — English, for the same reason `ConfirmOverlay`'s
#: are: this package knows no consuming application and cannot know its
#: language. Real consumers pass their own.
_DEFAULT_COPY_TEXT = "Copy"
_DEFAULT_CLEAR_TEXT = "Clear"

#: How the header badge renders the entry count. A format string rather than
#: a bare number, because the reference consumer's badge reads "340 EVENTS" —
#: the count carries a unit the panel has no way to guess. `{count}` is the
#: only field; anything else in the string is literal.
_DEFAULT_BADGE_FORMAT = "{count}"


class LogModel(Protocol):
    """
    @brief What `LogPanel` needs of a model, stated instead of implied.

    @details The reference consumer's three log panels all bind
    `runtime.log_list_model.LogListModel`, but this panel never names that
    class — it needs a `QAbstractItemModel` that also offers a change signal
    and the two actions the header buttons invoke. Written as a `Protocol`
    rather than an ABC because the model is a `QObject` subclass and cannot
    take a second metaclass (`widgets.style`'s module docstring covers the
    same constraint for widgets).
    """

    def rowCount(self, parent: QModelIndex = ...) -> int: ...
    def clear(self) -> None: ...
    def copyAllToClipboard(self) -> None: ...


class LogPanel(Card):
    """
    @brief A `Card` whose body is a log list, with an entry-count badge and
    Copy/Clear buttons in the header.

    @details
    **The line cap is not here, deliberately.** `LogListModel.MAX_ENTRIES`
    already trims oldest-first inside `append()`, and the reference consumer
    layers a second configurable trimmer on top of that. A `max_lines`
    parameter on this widget would be a third enforcement point for one
    rule — the widget would then either disagree with the model or silently
    do nothing, and both are worse than not offering it.

    **No auto-scroll, matching every existing consumer.** The QML kit this
    replaces had `autoScroll` with a follow-only-if-already-at-bottom guard;
    the QtWidgets port dropped it and all three panels have run without it
    since. Restoring it changes what users see, so it belongs in a migration
    task that can be reviewed and reverted, not smuggled in through a base
    class. Recorded as a candidate in `EPIC-007B`.

    Copy and Clear call straight through to the model, as the consumer's
    panel does — there is no presenter round-trip to preserve, and both are
    no-ops until a model is set.
    """

    def __init__(
        self,
        title: str,
        *,
        copy_text: str = _DEFAULT_COPY_TEXT,
        clear_text: str = _DEFAULT_CLEAR_TEXT,
        badge_format: str = _DEFAULT_BADGE_FORMAT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._model: LogModel | None = None
        self._badge_format = badge_format

        self._count_badge = Badge(self._format_count(0))
        self.header_actions.addWidget(self._count_badge)

        self.copy_button = StyledButton(copy_text, role=StyleRole.SECONDARY_BUTTON)
        self.copy_button.clicked.connect(self._copy_all)
        self.header_actions.addWidget(self.copy_button)

        self.clear_button = StyledButton(clear_text, role=StyleRole.SECONDARY_BUTTON)
        self.clear_button.clicked.connect(self._clear)
        self.header_actions.addWidget(self.clear_button)

        self.list_view = QListView()
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        apply_role(self.list_view, StyleRole.LIST_SURFACE)
        self.body_layout.addWidget(self.list_view, 1)

    @property
    def count_text(self) -> str:
        """What the header badge currently reads."""
        return self._count_badge.text()

    def set_log_model(self, model: LogModel) -> None:
        """
        @brief Binds a model, replacing any previous one.

        @details Disconnects the outgoing model's change signal first. The
        consumer's version of this method does not, so calling it twice
        leaves both connections live and `_update_count` runs once per bound
        model per appended line. No consumer rebinds today, which is why
        nobody has seen it; a base class that will be rebound by anyone is
        not the place to keep that latent.
        """
        previous = self._model
        if previous is not None:
            self._disconnect_count_signal(previous)

        self._model = model
        self.list_view.setModel(model)  # type: ignore[arg-type]
        changed = getattr(model, "countChanged", None)
        if changed is not None:
            changed.connect(self._update_count)
        self._update_count()

    def _disconnect_count_signal(self, model: LogModel) -> None:
        changed = getattr(model, "countChanged", None)
        if changed is None:
            return
        # Qt raises if the connection is already gone (model deleted, or
        # never connected because it exposed no such signal). Either way
        # the outcome wanted here — no live connection — already holds,
        # so there is nothing to recover from.
        with contextlib.suppress(RuntimeError, TypeError):
            changed.disconnect(self._update_count)

    def _format_count(self, count: int) -> str:
        return self._badge_format.format(count=count)

    def _update_count(self) -> None:
        count = 0 if self._model is None else self._model.rowCount(QModelIndex())
        self._count_badge.setText(self._format_count(count))

    def _copy_all(self) -> None:
        if self._model is not None:
            self._model.copyAllToClipboard()

    def _clear(self) -> None:
        if self._model is not None:
            self._model.clear()

    def _on_enabled_changed(self, enabled: bool) -> None:
        """`Surface`'s hook. Qt's cascade already greys the buttons; this
        additionally stops the count badge tracking a model that keeps
        appending behind a disabled panel — the one thing the cascade cannot
        do, since the signal is not a widget."""
        if self._model is None:
            return
        if enabled:
            self._disconnect_count_signal(self._model)
            changed = getattr(self._model, "countChanged", None)
            if changed is not None:
                changed.connect(self._update_count)
            self._update_count()
        else:
            self._disconnect_count_signal(self._model)
