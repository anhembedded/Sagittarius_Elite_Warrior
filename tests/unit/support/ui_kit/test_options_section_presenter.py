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
        self._save_succeeds = save_succeeds
        self.fields = _Fields()
        self._reload()

    def _load_from_config(self) -> None:
        self.fields.name = self._stored["name"]

    def _current_fields(self) -> str:
        return self.fields.name

    def _save(self) -> bool:
        if self._save_succeeds:
            self._stored["name"] = self.fields.name
        return self._save_succeeds

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


def test_revert_puts_the_saved_values_back(qapp) -> None:
    page = _Page({"name": "a"})
    page.fields.edit("b")

    page.revert()

    assert page.fields.name == "a"
    assert not page.is_dirty()


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
