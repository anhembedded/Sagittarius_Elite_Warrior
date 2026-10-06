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
reserves, at the window's build time. A command that *is* one of those
platform commands, such as Save bot (Save, Ctrl+S on Windows), names it in
`standard_shortcut` instead: the name of a `QKeySequence.StandardKey` member,
which the window resolves, so the platform decides the key.

The catalogue of commands, with their menus, shortcuts and confirmations, is
HLD §11.2.3.

Checkable commands that name one `exclusive_group` are one choice among
several, such as View → Spot market or Futures market: the window puts them in one
exclusive `QActionGroup`, so checking one unchecks the others and checking
the checked one keeps it (Qt `QActionGroup`; MS `cmd-menus`, "option
buttons" in a menu).

Related commands of one menu name one `group` (`BOT-157`): the menu shows
each group together, in the order its first command was contributed, with
one separator between adjacent groups and none at either end (MS
`cmd-menus`, "group related items"). A command naming no group is in the
`None` group, so every command declared before groups existed stays where it
was.

A command may name an `icon` (`BOT-164`): the stem of a file under
`support/ui_kit/assets/icons/`. The window sets it on the command's one
action, so the toolbar button and the menu entry carry it, and the mode's
toolbar writes the text beside it, so the command reads as a button.

Plausible extensions, each a local change: a command whose text follows its state, such as
Pause / Resume (one field naming the alternate text); a group's order key, or
a group's title shown as a section header where the platform has one.
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
    #: A `QKeySequence.StandardKey` member's name ("Save"), for a command that
    #: is that platform command; never together with `shortcut`.
    standard_shortcut: str | None = None
    checkable: bool = False
    needs_input: bool = False
    confirm: CommandConfirmation | None = None
    #: The choice this checkable command is one option of; the window makes
    #: every command naming the same group one exclusive `QActionGroup`.
    exclusive_group: str | None = None
    #: The related commands it sits with in its menu; a separator divides
    #: one group from the next. `None` is the group of commands naming none.
    group: str | None = None
    #: An icon file stem ("play"); `None` is an action of text alone.
    icon: str | None = None

    def __post_init__(self) -> None:
        if self.shortcut is not None and self.standard_shortcut is not None:
            raise ValueError(
                f"command {self.command_id!r} names both a shortcut and a "
                "standard shortcut; a command has one key"
            )
        if self.exclusive_group is not None and not self.checkable:
            raise ValueError(
                f"command {self.command_id!r} names an exclusive group but is "
                "not checkable; only a checked option can exclude the others"
            )
