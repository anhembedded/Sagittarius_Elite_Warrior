"""`EPIC-047D` - Tools -> Options -> VPS Link: create, edit and delete a connection, switch its protocol, write nothing until Apply."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
    LinkProtocol,
)
from Sagittarius_Elite_Warrior.src.shell.link_options.link_options_page import (
    LinkOptionsPage,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)

HOME = LinkProfile(name="home", host="vps.example")


def _find(page: LinkOptionsPage, kind: type, name: str):
    found = page.widget().findChild(kind, f"options::link::{name}")
    assert found is not None, name
    return found


def _type(edit: QLineEdit, text: str) -> None:
    edit.setText(text)
    edit.textEdited.emit(text)


def _page(
    *profiles: LinkProfile, selected: str | None = None
) -> tuple[LinkOptionsPage, LinkProfiles]:
    saved = LinkProfiles()
    saved.replace(tuple(profiles), selected)
    return LinkOptionsPage(saved), saved


def test_the_page_satisfies_the_dialogs_contract(qapp) -> None:
    assert isinstance(_page()[0], IOptionsSection)


def test_the_page_opens_on_the_saved_profile_and_is_clean(qapp) -> None:
    page, _ = _page(HOME, selected="home")

    assert _find(page, QLineEdit, "host").text() == "vps.example"
    assert _find(page, QCheckBox, "in_use").isChecked()
    assert not page.is_dirty()
    assert page.validation_message() is None


def test_with_no_profile_the_page_says_how_to_start(qapp) -> None:
    page, _ = _page()

    assert not _find(page, QPushButton, "remove").isEnabled()
    assert (
        not page.widget()
        .findChild(QLineEdit, "options::link::host")
        .isVisibleTo(page.widget())
    )  # type: ignore[union-attr]


def test_adding_a_connection_is_dirty_names_what_is_missing_and_saves_nothing(
    qapp,
) -> None:
    page, saved = _page()
    told: list[bool] = []
    page.set_change_listener(lambda: told.append(True))

    _find(page, QPushButton, "add").click()

    assert page.is_dirty() and told
    assert "host" in str(page.validation_message())
    assert saved.profiles == ()


def test_editing_the_fields_and_applying_writes_the_profile(qapp) -> None:
    page, saved = _page()
    _find(page, QPushButton, "add").click()

    _type(_find(page, QLineEdit, "name"), "vps")
    _type(_find(page, QLineEdit, "host"), "203.0.113.7")
    _find(page, QSpinBox, "port").setValue(2200)
    page.apply()

    assert page.validation_message() is None
    assert saved.profiles == (LinkProfile(name="vps", host="203.0.113.7", port=2200),)
    assert saved.selected_name == "vps"
    assert not page.is_dirty()


def test_choosing_a_key_file_stores_its_path_and_nothing_else(qapp) -> None:
    page, saved = _page(HOME, selected="home")

    _find(page, QRadioButton, "key_file_radio").setChecked(True)
    _type(_find(page, QLineEdit, "key_file"), "C:\\Users\\me\\.ssh\\id_ed25519")
    page.apply()

    profile = saved.profiles[0]
    assert profile.key_source is KeySource.KEY_FILE
    assert profile.key_file == "C:\\Users\\me\\.ssh\\id_ed25519"


def test_a_pasted_key_is_refused_by_the_page(qapp) -> None:
    page, _ = _page(HOME, selected="home")
    _find(page, QRadioButton, "key_file_radio").setChecked(True)

    _type(_find(page, QLineEdit, "key_file"), "-----BEGIN OPENSSH PRIVATE KEY-----")

    assert "file" in str(page.validation_message())


def test_the_protocol_is_a_choice_the_profile_follows(qapp) -> None:
    page, saved = _page(HOME)
    combo = _find(page, QComboBox, "protocol")

    assert combo.findData(LinkProtocol.SSH.value) >= 0
    combo.setCurrentIndex(combo.findData(LinkProtocol.SSH.value))
    page.apply()

    assert saved.profiles[0].protocol is LinkProtocol.SSH


def test_removing_the_selected_connection_and_applying_forgets_it_and_the_in_use_choice(
    qapp,
) -> None:
    page, saved = _page(HOME, selected="home")

    _find(page, QPushButton, "remove").click()
    assert page.is_dirty()
    page.apply()

    assert saved.profiles == () and saved.selected_name is None


def test_two_connections_with_one_name_cannot_be_applied(qapp) -> None:
    page, _ = _page(HOME)
    _find(page, QPushButton, "add").click()

    _type(_find(page, QLineEdit, "name"), "home")
    _type(_find(page, QLineEdit, "host"), "other.example")

    assert "home" in str(page.validation_message())


def test_the_in_use_connection_follows_the_checkbox(qapp) -> None:
    other = LinkProfile(name="other", host="o.example")
    page, saved = _page(HOME, other, selected="home")
    page.widget().findChild(QListWidget, "options::link::list").setCurrentRow(1)

    _find(page, QCheckBox, "in_use").setChecked(True)
    page.apply()

    assert saved.selected_name == "other"


def test_revert_puts_the_page_back_to_the_saved_profiles(qapp) -> None:
    page, _ = _page(HOME, selected="home")
    _type(_find(page, QLineEdit, "host"), "changed.example")
    assert page.is_dirty()

    page.revert()

    assert not page.is_dirty()
    assert _find(page, QLineEdit, "host").text() == "vps.example"


def test_the_form_has_no_field_for_a_password_or_a_passphrase(qapp) -> None:
    page, _ = _page(HOME)

    edits = page.widget().findChildren(QLineEdit)

    assert edits and all(e.echoMode() == QLineEdit.EchoMode.Normal for e in edits)
    assert not [e.objectName() for e in edits if "pass" in e.objectName()]
