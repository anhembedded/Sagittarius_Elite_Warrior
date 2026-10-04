"""`EPIC-033E` — what every page of Tools → Options does the same way.

A page is dirty while its fields differ from the last saved ones; a save that
fails leaves it dirty; Cancel puts the saved values back; every edit reaches
the dialog's listener. Driven through a minimal real subclass with a real
`QObject` view model, the way the Trading and Market Data pages use the base.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal, SignalInstance
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.options_section_presenter import (
    OptionsSectionPresenter,
)


class _Fields(QObject):
    name_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.name = ""

    def edit(self, name: str) -> None:
        self.name = name
        self.name_changed.emit()


class _Page(OptionsSectionPresenter[str]):
    def __init__(self, stored: dict[str, str], *, save_succeeds: bool = True) -> None:
        super().__init__(QWidget(), Mock(), title="Sample")
        self._stored = stored
        self._live = dict(stored)
        self._save_succeeds = save_succeeds
        self.fields = _Fields()
        self._reload()

    def _load_from_config(self) -> None:
        self.fields.name = self._stored["name"]

    def _current_fields(self) -> str:
        return self.fields.name

    def _save(self) -> bool:
        # Like a real page: the value goes into the live store first, and
        # only the disk write can fail.
        self._live["name"] = self.fields.name
        if self._save_succeeds:
            self._stored["name"] = self.fields.name
        return self._save_succeeds

    def _undo_unsaved_writes(self) -> None:
        self._live["name"] = self._saved_fields

    def _change_signals(self) -> tuple[SignalInstance, ...]:
        return (self.fields.name_changed,)


class _PageMissingAHook(OptionsSectionPresenter[str]):
    def __init__(self) -> None:
        super().__init__(QWidget(), Mock(), title="Broken")


def test_a_page_is_dirty_only_while_its_fields_differ_from_the_saved_ones(
    qapp,
) -> None:
    page = _Page({"name": "a"})
    assert not page.is_dirty()

    page.fields.edit("b")
    assert page.is_dirty()

    page.fields.edit("a")
    assert not page.is_dirty()


def test_apply_saves_and_takes_the_new_values_as_saved(qapp) -> None:
    stored = {"name": "a"}
    page = _Page(stored)
    page.fields.edit("b")

    page.apply()

    assert stored == {"name": "b"}
    assert not page.is_dirty()


def test_a_save_that_fails_leaves_the_page_dirty(qapp) -> None:
    stored = {"name": "a"}
    page = _Page(stored, save_succeeds=False)
    page.fields.edit("b")

    page.apply()

    assert stored == {"name": "a"}
    assert page.is_dirty()


def test_a_save_that_fails_leaves_nothing_unsaved_in_memory(qapp) -> None:
    """PR #348 review: the live store had kept the value that never reached
    disk, so the session ran on it and Cancel took it as saved."""
    page = _Page({"name": "a"}, save_succeeds=False)
    page.fields.edit("b")

    page.apply()

    assert page._live == {"name": "a"}
    assert page.fields.name == "b"


def test_revert_puts_the_saved_values_back(qapp) -> None:
    page = _Page({"name": "a"})
    page.fields.edit("b")

    page.revert()

    assert page.fields.name == "a"
    assert not page.is_dirty()


def test_a_new_dialogs_listener_replaces_the_previous_one(qapp) -> None:
    """Tools → Options builds a new dialog on every open; the closed one must
    stop hearing the page's edits."""
    page = _Page({"name": "a"})
    first: list[None] = []
    second: list[None] = []
    page.set_change_listener(lambda: first.append(None))
    page.set_change_listener(lambda: second.append(None))

    page.fields.edit("b")

    assert (len(first), len(second)) == (0, 1)


def test_every_edit_reaches_the_dialogs_listener(qapp) -> None:
    page = _Page({"name": "a"})
    heard: list[None] = []
    page.set_change_listener(lambda: heard.append(None))

    page.fields.edit("b")
    page.fields.edit("c")

    assert len(heard) == 2


def test_a_page_satisfies_the_dialogs_contract(qapp) -> None:
    page = _Page({"name": "a"})

    assert isinstance(page, IOptionsSection)
    assert page.title == "Sample"
    assert page.widget() is page.view
    assert page.validation_message() is None


def test_a_page_that_forgets_a_hook_names_it(qapp) -> None:
    page = _PageMissingAHook()

    with pytest.raises(NotImplementedError, match="_load_from_config"):
        page.revert()
