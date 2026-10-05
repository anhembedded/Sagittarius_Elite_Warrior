"""What a presenter binds the commands its module contributed through
(`EPIC-033D`); the presenter's side is `command_presenter.py`.

The binder is the Engine's `ActionRegistry`, which has exactly this `bind`.
A `Protocol`, because its implementer is third-party (reason (c),
`architecture-rule.md` §2.1). It lives here, not in `core/contracts`, because
its signature names Qt's `SignalInstance`, which only presentation may know.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance


class ICommandBinder(Protocol):
    """Connects one contributed command to what performs it."""

    def bind(
        self,
        action_id: str,
        handler: Callable[[bool], None],
        *,
        enabled: SignalInstance | None = None,
        checked: SignalInstance | None = None,
        initially_enabled: bool = True,
    ) -> None:
        """`handler` gets the checked state (`False` for a plain command).
        `enabled` and `checked` keep the action in step with the presenter;
        `initially_enabled` holds until `enabled` first fires."""
        ...
