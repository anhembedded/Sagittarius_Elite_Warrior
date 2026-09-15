"""`EPIC-025` PR 1.5a — the Welcome surface, the first screen the shell owns.

Three things are worth holding, and the third is the one a user would meet:

1. the screen says what the application is, including **which venue this run
   talks to** — a user who does not know whether they are on Testnet is a user
   one click from a real order;
2. **Start** raises an intent on the bus and decides nothing itself, so *Main*
   can point it somewhere else (a real login) without this screen changing;
3. it is the **default route**, which is the user-visible half of ADR D13.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    SHELL_CONTRIBUTOR_ID,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.welcome.start_requested_event import (
    StartRequested,
)
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_presenter import (
    WelcomePresenter,
)
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_screen import (
    WELCOME_ROUTE,
    welcome_screen,
)
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_view import WelcomeView

_CONFIG = {
    ConfigKeys.APP_NAME.value: "Sagittarius Elite Warrior",
    ConfigKeys.APP_VERSION.value: "9.9.9",
    # Real venue values: an unknown one makes `resolve_market_data_venue`
    # warn and fall back, and a test asserting on the fallback would be
    # asserting on its own typo.
    ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: "futures_testnet",
    ConfigKeys.EXCHANGE_TRADING_VENUE.value: "futures_testnet",
}


class _Writer(IConfigWriter):
    """What the switch writes through, recorded rather than mocked: *whether
    `save()` was called* is half the guarantee, and a `Mock` would answer
    `set()` and `save()` identically whether or not the code called both."""

    def __init__(self, *, fails: bool = False) -> None:
        self.written: list[tuple[str, object]] = []
        self.saves = 0
        self._fails = fails

    def set(self, key: str, value: object) -> None:
        self.written.append((key, value))

    def save(self) -> None:
        if self._fails:
            raise OSError("read-only config")
        self.saves += 1


class _Config:
    """The one thing the Presenter reads, as a double with no `Mock` reach:
    a `Mock().get()` would answer a `Mock` for every key and the screen would
    render `<Mock id=...>` as the app's name."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def get(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)


class _Bus:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)

    def subscribe(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def on(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


def _container(
    config: dict[str, object] | None = None, *, writer: _Writer | None = None
) -> Mock:
    """A container that answers what `BasePresenter` resolves plus the config
    writer — the config, the bus and the writer are real doubles, because the
    Presenter's behaviour depends on all three."""
    bus = _Bus()
    values = dict(_CONFIG)
    values.update(config or {})
    config_double = _Config(values)
    config_writer = writer or _Writer()

    def resolve(abstract):
        name = getattr(abstract, "__name__", "")
        if name == "IEventBus":
            return bus
        if name == "IConfig":
            return config_double
        if name == "IConfigWriter":
            return config_writer
        return Mock()

    container = Mock()
    container.resolve.side_effect = resolve
    container.bus = bus
    container.config_double = config_double
    container.config_writer = config_writer
    return container


@pytest.fixture
def view(qapp) -> WelcomeView:
    return WelcomeView()


class TestTheScreenItself:
    def test_the_workspace_is_the_surfaces_centre(self, view: WelcomeView) -> None:
        """A `WorkbenchSurface` like every other screen, so it gets the
        environment banner and a saved perspective for free."""
        assert view.surface.centralWidget() is not None
        assert Place.WORKSPACE in view.surface.accepts()

    def test_it_names_the_application_and_its_version(self, view: WelcomeView) -> None:
        view.show_application("Sagittarius Elite Warrior", "9.9.9")

        title = view.findChild(QLabel, "lblWelcomeTitle")
        subtitle = view.findChild(QLabel, "lblWelcomeSubtitle")
        assert title.text() == "Sagittarius Elite Warrior"
        assert "9.9.9" in subtitle.text()

    def test_start_is_a_button_the_keyboard_reaches(self, view: WelcomeView) -> None:
        """`setDefault(True)`: Enter starts the app, which is the Efficiency
        principle's keyboard path for the one action on the screen."""
        button = view.findChild(QPushButton, "btnStart")

        assert button is not None
        assert button.isDefault() is True

    def test_pressing_start_emits_the_signal_and_decides_nothing(
        self, view: WelcomeView
    ) -> None:
        raised: list[int] = []
        view.start_requested.connect(lambda: raised.append(1))

        view.findChild(QPushButton, "btnStart").click()

        assert raised == [1]


class TestThePresenter:
    def test_it_fills_the_screen_from_configuration(self, qapp) -> None:
        view = WelcomeView()

        WelcomePresenter(view, _container())

        subtitle = view.findChild(QLabel, "lblWelcomeSubtitle").text()
        assert view.findChild(QLabel, "lblWelcomeTitle").text() == (
            "Sagittarius Elite Warrior"
        )
        assert "9.9.9" in subtitle

    def test_it_says_which_venue_this_run_talks_to(self, qapp) -> None:
        """Both venues, because they are independent settings (ADR §2): where
        prices come from and where an order would go are two decisions, and a
        screen naming only one would be the more dangerous half hidden."""
        view = WelcomeView()

        WelcomePresenter(view, _container())

        subtitle = view.findChild(QLabel, "lblWelcomeSubtitle").text()
        assert "market data: futures_testnet" in subtitle
        assert "trading: futures_testnet" in subtitle

    def test_start_becomes_an_intent_on_the_bus(self, qapp) -> None:
        view = WelcomeView()
        container = _container()
        # Held in a local on purpose: a `BasePresenter` is a `QObject`, and an
        # unreferenced one is collected the moment this line ends — taking its
        # signal connections with it, so the click below would reach nothing.
        # In the app `PresenterManager` is what owns it.
        presenter = WelcomePresenter(view, container)

        view.findChild(QPushButton, "btnStart").click()

        assert presenter is not None

        assert [type(event) for event in container.bus.published] == [StartRequested]

    def test_it_publishes_nothing_until_the_user_asks(self, qapp) -> None:
        container = _container()

        presenter = WelcomePresenter(WelcomeView(), container)

        assert container.bus.published == []
        assert presenter is not None


class TestTheContribution:
    def test_it_is_the_shells_own_and_the_default_route(self) -> None:
        contribution = welcome_screen()

        assert contribution.contributor_id == SHELL_CONTRIBUTOR_ID
        assert contribution.route == WELCOME_ROUTE
        assert contribution.is_default is True

    def test_it_has_a_sidebar_entry_before_the_trading_screens(self) -> None:
        nav = welcome_screen().nav

        assert nav is not None
        assert nav.title == "Welcome"
        assert nav.item_sequence < 10

    def test_building_the_contribution_imports_no_widget(self) -> None:
        """The factories are lazy, and this is the assertion that keeps them
        so: `shell/contribution_assembly.py` is imported by the **headless**
        entry point, and a `WelcomeView` named at module level there would
        make `python -m ...main sync` import Qt for a screen it never shows."""
        contribution = welcome_screen()

        assert callable(contribution.view_factory)
        assert callable(contribution.presenter_factory)
        assert "WelcomeView" not in repr(contribution.view_factory)


class TestTheDeveloperModeSwitch:
    """ADR D14: the switch writes `user_config.json` and offers a restart.
    `dev.mode` is read once at boot — it gates a surface, so a value that
    changed mid-run would mean loading or unloading a module."""

    def test_it_starts_where_configuration_left_it(self, qapp) -> None:
        view = WelcomeView()
        container = _container({ConfigKeys.DEV_MODE.value: True})

        presenter = WelcomePresenter(view, container)

        assert view.findChild(QCheckBox, "chkDeveloperMode").isChecked() is True
        assert presenter is not None

    def test_showing_the_stored_value_is_not_a_change_the_user_made(self, qapp) -> None:
        """`setChecked()` emits `toggled`, so a Presenter that reported the
        value it had just read would write the file on every boot — and turn
        "the app started" into "the user changed a setting"."""
        container = _container({ConfigKeys.DEV_MODE.value: True})

        presenter = WelcomePresenter(WelcomeView(), container)

        assert container.config_writer.written == []
        assert container.config_writer.saves == 0
        assert presenter is not None

    def test_toggling_it_writes_and_saves(self, qapp) -> None:
        view = WelcomeView()
        container = _container()
        presenter = WelcomePresenter(view, container)

        view.findChild(QCheckBox, "chkDeveloperMode").setChecked(True)

        assert container.config_writer.written == [(ConfigKeys.DEV_MODE.value, True)]
        assert container.config_writer.saves == 1
        assert presenter is not None

    def test_the_restart_offer_appears_only_after_the_write(self, qapp) -> None:
        view = WelcomeView()
        container = _container()
        presenter = WelcomePresenter(view, container)
        notice = view.findChild(QLabel, "lblRestartNotice")
        button = view.findChild(QPushButton, "btnRestartNow")

        assert notice.isVisible() is False
        assert button.isVisible() is False

        view.findChild(QCheckBox, "chkDeveloperMode").setChecked(True)

        assert notice.isVisibleTo(view) is True
        assert button.isVisibleTo(view) is True
        assert presenter is not None

    def test_a_failed_save_offers_no_restart_and_puts_the_switch_back(
        self, qapp
    ) -> None:
        """The notice is a fact about the file on disk. A failed write with a
        cheerful "restart to apply" beside it is a lie the user acts on."""
        view = WelcomeView()
        container = _container(writer=_Writer(fails=True))
        presenter = WelcomePresenter(view, container)

        view.findChild(QCheckBox, "chkDeveloperMode").setChecked(True)

        assert view.findChild(QLabel, "lblRestartNotice").isVisibleTo(view) is False
        assert view.findChild(QCheckBox, "chkDeveloperMode").isChecked() is False
        assert presenter is not None
