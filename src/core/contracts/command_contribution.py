"""A command a module offers: one `QAction` in the workbench (`EPIC-033D`).

A command is something the user does, such as Enable live trading, Emergency
stop or Sync history. On a Windows desktop it is one action that its menu
entry, its toolbar button and its shortcut share, so its text and enabled
state cannot drift between them (Qt, "Actions"; MS `cmd-menus`). A module
declares it here as data, in `contribute()`. The window turns it into the
Engine's `ActionDescriptor`, and the presenter that performs it binds a
handler once it is built (`support/ui_kit/command_binding.py`).

Plain data, with no Qt and no Engine type: `core/contracts` imports nothing
from the Engine but the Shared Kernel. The shortcut is Qt's portable text
("F8", "Ctrl+L"); the Engine's shortcut policy refuses a key the platform
reserves, at the window's build time.

The catalogue of commands, with their menus, shortcuts and confirmations, is
HLD §11.2.3.

Plausible extensions, each a local change: an icon name (one field and one
line in the window); a command whose text follows its state, such as
Pause / Resume (one field naming the alternate text).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandConfirmation:
    """The question a risky command asks first (MS `mess-confirm`). The
    answer names the action, never OK or Yes; Cancel is the default."""

    title: str
    consequence: str
    accept_text: str


@dataclass(frozen=True, slots=True)
class CommandContribution:
    """One command of one module."""

    contributor_id: str
    #: Unique across the application.
    command_id: str
    #: Menu text: sentence case, one `&` access key, "…" only if it asks for
    #: more input (`needs_input`).
    text: str
    #: The menus it sits in, outermost first: `("T&rade",)`.
    menu_path: tuple[str, ...]
    #: The mode it belongs to (a screen's route), or `None` for every mode.
    mode: str | None = None
    #: Also a button on its mode's toolbar.
    on_toolbar: bool = False
    shortcut: str | None = None
    checkable: bool = False
    needs_input: bool = False
    confirm: CommandConfirmation | None = None
