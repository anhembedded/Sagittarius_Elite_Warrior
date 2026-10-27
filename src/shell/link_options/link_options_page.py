"""Tools → Options → VPS Link (`EPIC-047D`): create, edit and delete connection profiles.

A list of the saved connections beside the fields of the one selected (`ProfileForm`), and the one
the VPS Bots tab uses. The page edits a **draft** and writes it to `LinkProfiles` only on OK or Apply,
never on the click itself (the dialog's own contract, `IOptionsSection`); a draft the repository
refuses (`problem_of`) keeps the dialog from applying and says why. It stores no password,
passphrase or key — the form has no field for one. Switching the protocol is the form's combo; a
second protocol is a member of `LinkProtocol` and an adapter, no change here. Nothing here takes long
enough to need a coordinator: the page never connects.

An `IOptionsSection` (satisfied structurally).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
    problem_of,
)
from Sagittarius_Elite_Warrior.src.shell.link_options import link_options_words as words
from Sagittarius_Elite_Warrior.src.shell.link_options.profile_form import ProfileForm
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)


class LinkOptionsPage:
    def __init__(self, saved: LinkProfiles) -> None:
        self._saved = saved
        self._listener: Callable[[], None] | None = None
        self._draft: list[LinkProfile] = []
        self._in_use: int | None = None
        self._showing = False
        self._widget = QWidget()
        self._widget.setObjectName("options::link")
        self._list = QListWidget()
        self._list.setObjectName("options::link::list")
        self._add = QPushButton(words.ADD_TEXT)
        self._add.setObjectName("options::link::add")
        self._remove = QPushButton(words.REMOVE_TEXT)
        self._remove.setObjectName("options::link::remove")
        self._form = ProfileForm()
        self._in_use_box = QCheckBox(words.IN_USE_TEXT)
        self._in_use_box.setObjectName("options::link::in_use")
        self._hint = plain_label(words.EMPTY_HINT)
        self._hint.setObjectName("options::link::hint")
        self._hint.setWordWrap(True)
        self._lay_out()
        self._list.currentRowChanged.connect(self._row_changed)
        self._add.clicked.connect(self._add_profile)
        self._remove.clicked.connect(self._remove_profile)
        self._form.set_listener(self._form_edited)
        self._in_use_box.toggled.connect(self._in_use_toggled)
        self.revert()

    # -- IOptionsSection -------------------------------------------------------

    @property
    def title(self) -> str:
        return words.TITLE

    def widget(self) -> QWidget:
        return self._widget

    def apply(self) -> None:
        self._saved.replace(tuple(self._draft), self._in_use_name())

    def revert(self) -> None:
        self._draft = list(self._saved.profiles)
        names = [p.name for p in self._draft]
        self._in_use = (
            names.index(self._saved.selected_name)
            if self._saved.selected_name in names
            else None
        )
        self._fill_list(select=0 if self._draft else None)

    def is_dirty(self) -> bool:
        return (
            tuple(self._draft) != self._saved.profiles
            or self._in_use_name() != self._saved.selected_name
        )

    def validation_message(self) -> str | None:
        seen: set[str] = set()
        for profile in self._draft:
            problem = problem_of(profile)
            if problem is not None:
                return f"{profile.name or words.NEW_NAME}: {problem}"
            if profile.name in seen:
                return f"Two connections are called {profile.name}."
            seen.add(profile.name)
        return None

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        self._listener = listener

    # -- internals -------------------------------------------------------------

    def _lay_out(self) -> None:
        buttons = QHBoxLayout()
        buttons.addWidget(self._add)
        buttons.addWidget(self._remove)
        buttons.addStretch(1)
        left = QVBoxLayout()
        list_label = plain_label(words.LIST_LABEL)
        list_label.setBuddy(self._list)
        left.addWidget(list_label)
        left.addWidget(self._list, 1)
        left.addLayout(buttons)
        right = QVBoxLayout()
        right.addWidget(self._hint)
        right.addWidget(self._form)
        right.addWidget(self._in_use_box)
        right.addStretch(1)
        layout = QHBoxLayout(self._widget)
        layout.addLayout(left, 1)
        layout.addLayout(right, 2)

    def _in_use_name(self) -> str | None:
        return None if self._in_use is None else self._draft[self._in_use].name

    def _fill_list(self, *, select: int | None) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for profile in self._draft:
            self._list.addItem(QListWidgetItem(profile.name or words.NEW_NAME))
        self._list.blockSignals(False)
        self._list.setCurrentRow(select if select is not None else -1)
        self._row_changed(self._list.currentRow())

    def _row_changed(self, row: int) -> None:
        has_row = 0 <= row < len(self._draft)
        self._form.setVisible(has_row)
        self._in_use_box.setVisible(has_row)
        self._hint.setVisible(not has_row)
        self._remove.setEnabled(has_row)
        if has_row:
            self._showing = True
            self._form.show_profile(self._draft[row])
            self._in_use_box.setChecked(self._in_use == row)
            self._showing = False

    def _form_edited(self) -> None:
        row = self._list.currentRow()
        if not 0 <= row < len(self._draft):
            return
        edited = self._form.read_profile()
        self._draft[row] = edited
        item = self._list.item(row)
        if item is not None:
            item.setText(edited.name or words.NEW_NAME)
        self._announce()

    def _in_use_toggled(self, checked: bool) -> None:
        if self._showing:
            return
        row = self._list.currentRow()
        if checked:
            self._in_use = row
        elif self._in_use == row:
            self._in_use = None
        self._announce()

    def _add_profile(self) -> None:
        taken = {p.name for p in self._draft}
        number = len(self._draft) + 1
        while f"vps-{number}" in taken:
            number += 1
        fresh = LinkProfile(name=f"vps-{number}", host="")
        self._draft.append(fresh)
        if self._in_use is None and len(self._draft) == 1:
            self._in_use = 0
        self._fill_list(select=len(self._draft) - 1)
        self._announce()

    def _remove_profile(self) -> None:
        row = self._list.currentRow()
        if not 0 <= row < len(self._draft):
            return
        del self._draft[row]
        if self._in_use == row:
            self._in_use = None
        elif self._in_use is not None and self._in_use > row:
            self._in_use -= 1
        self._fill_list(select=min(row, len(self._draft) - 1) if self._draft else None)
        self._announce()

    def _announce(self) -> None:
        if self._listener is not None:
            self._listener()
