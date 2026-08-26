"""
@brief `StyledLabel` — the abstract gate of the token-styled label family.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from ..style import StyleRole, WidgetState, apply_role


class StyledLabel(QLabel):
    """
    @brief A `QLabel` that renders through `apply_role()` and can re-render
    itself in a different `WidgetState`. Abstract — instantiate
    `SectionLabel` or `Badge`.

    @details
    This package's other four controls deliberately share **no** base, on
    the grounds that "calls `apply_role()` once" is not an abstraction. This
    one earns its place by doing something more than that: its two
    subclasses both need to re-render *after* construction, in a state that
    changes at runtime — a badge switching to its emphasised form when its
    tab becomes current, a section label greying out with its group. That
    is `set_state()` below, and it is real shared behaviour rather than a
    shared constructor.

    If a future subclass needs only the constructor, it belongs on `QLabel`
    directly, not here. And per `EPIC-007C`'s own requirement 2: had these
    two turned out to share nothing, this layer was to be deleted rather
    than kept as an empty tier.

    Abstract by a `type(self) is` guard, not `abc` — the same PySide6/
    Shiboken limitation `Surface` and `Overlay` were each settled by, and
    for the same verified reason (`ABCMeta` does not reliably block
    instantiation of a Qt widget subclass under this binding).
    """

    def __init__(
        self,
        text: str = "",
        *,
        role: StyleRole,
        parent: QWidget | None = None,
    ) -> None:
        if type(self) is StyledLabel:
            raise TypeError(
                "StyledLabel is abstract — instantiate SectionLabel or Badge."
            )
        super().__init__(text, parent)
        self._role = role
        self._state = WidgetState.NORMAL
        apply_role(self, role)

    @property
    def role(self) -> StyleRole:
        return self._role

    @property
    def state(self) -> WidgetState:
        return self._state

    def set_state(self, state: WidgetState) -> None:
        """@brief Re-renders this label in a different structural state."""
        self._state = state
        apply_role(self, self._role, state=state)
