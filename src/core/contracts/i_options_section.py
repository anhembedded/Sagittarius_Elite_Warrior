"""One page of Tools → Options, contributed by a module (`EPIC-033E`).

The Options dialog owns the commit buttons and what they mean (MS
`win-dialog-box`): OK applies every page and closes, Cancel reverts every page
and closes, Apply applies and stays, and Apply is enabled only while a page
holds edits. So a page never saves on its own. This is the Engine's
`IOptionsPage` contract, restated here because `core/contracts` imports
nothing from the Engine but the Shared Kernel; any object satisfying one
satisfies the other.

A `Protocol`: the implementers are presenters, `QObject`s, and Shiboken
forbids a second `QObject`-derived base and conflicts with `ABCMeta`
(`architecture-rule.md` §2.1, reason (a)).

Plausible extensions, each a local change: a page that asks before leaving
it (one method here, one call in the dialog); a page with a help link (one
property).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


@runtime_checkable
class IOptionsSection(Protocol):
    """What the Options dialog needs of a page."""

    @property
    def title(self) -> str:
        """The section name in the list on the left. Title case, no "&"."""
        ...

    def widget(self) -> QWidget:
        """The page itself, built once."""
        ...

    def apply(self) -> None:
        """Writes the edited values. Called only when `is_dirty()`."""
        ...

    def revert(self) -> None:
        """Puts the page back to the saved values."""
        ...

    def is_dirty(self) -> bool:
        """Whether the page holds edits not yet applied."""
        ...

    def validation_message(self) -> str | None:
        """Why the page's values cannot be applied, or `None`."""
        ...

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        """The dialog's callback for any edit. Called once, before it shows."""
        ...
