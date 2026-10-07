"""`BOT-125`/`EPIC-028C` — the trading venue toggles on the Trading settings
section.

Split off `tests/unit/presentation/ui/screens/test_settings_venue_controls.py`,
keeping only what this module owns. `market_data`'s venue moved to
`tests/unit/modules/market_data/ui/settings/test_market_data_settings_venue.py`.

Since `EPIC-028C` the page shows one toggle per venue that can place orders,
and Save writes `exchange.trading_venues`, the list boot reads. These tests
hold the control to what makes it honest: it refuses rather than
half-applies while any venue's live session runs; it shows what the app is
really running on; what it saves is what the next boot serves.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_presenter import (
    TradingSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view import (
    TradingSettingsView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.settings.primary_venue_contexts import (
    primary_venue_contexts,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET
_LIST = ConfigKeys.EXCHANGE_TRADING_VENUES.value
_SCALAR = ConfigKeys.EXCHANGE_TRADING_VENUE.value


class _FakeConfig:
    """Stores what it is given, so the assertions can be about values
    rather than about `set` having been called with something."""

    def __init__(self, initial: dict | None = None) -> None:
        self.values: dict = {}
        self.values.update(initial or {})
        self.save_count = 0

    def get(self, key, default=None, cast=None):
        return self.values.get(key, default)

    def get_all(self):
        return dict(self.values)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.save_count += 1


class _Sessions:
    """Each venue's trading session, as `IVenueTradingPorts` serves them."""

    def __init__(self) -> None:
        self.futures = FakeTradingSession()
        self.spot = FakeTradingSession()

    def ports(self) -> FakeVenueTradingPorts:
        return FakeVenueTradingPorts(
            fake_venue_ports(_FUTURES, trading_session=self.futures),
            fake_venue_ports(_SPOT, trading_session=self.spot),
        )


@pytest.fixture
def credentials_provider() -> Mock:
    provider = Mock(spec=IExchangeCredentialsProvider)
    provider.resolve.return_value = ResolvedCredentials(None, CredentialsSource.NONE)
    return provider


def _presenter(request, config, sessions, credentials_provider, notifier=None):
    container = Mock()
    notifier = notifier or RecordingNotifier()

    def resolve(interface):
        if interface is IConfig or getattr(interface, "__name__", "") == "IConfig":
            return config
        if interface is IVenueContexts:
            return primary_venue_contexts(credentials_provider)
        if interface is IVenueTradingPorts:
            return sessions.ports()
        if interface is IAccountSnapshot:
            return FakeAccountSnapshot()
        if interface is INotifier:
            return notifier
        return Mock()

    container.resolve.side_effect = resolve
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)
    return TradingSettingsPresenter(view, container), view


def test_every_orderable_venue_has_a_toggle_and_disabled_has_none(
    qapp, request, credentials_provider
):
    """A venue gaining order submission (`TradingVenue` is designed to gain a
    `MAINNET` member, `EPIC-021` ADR §3) gets a toggle; turning trading off is
    unticking every box, not a `DISABLED` toggle."""
    _presenter_obj, view = _presenter(
        request, _FakeConfig(), _Sessions(), credentials_provider
    )

    assert set(view._venue_toggles) == {
        venue for venue in TradingVenue if venue.supports_order_submission
    }
    assert all(toggle.text().strip() for toggle in view._venue_toggles.values())


def test_the_configured_list_is_shown_on_load(qapp, request, credentials_provider):
    config = _FakeConfig({_LIST: [_SPOT.value], _SCALAR: _FUTURES.value})
    presenter, view = _presenter(request, config, _Sessions(), credentials_provider)

    assert presenter._settings_view_model.enabledVenues == [_SPOT.value]
    assert view._venue_toggles[_SPOT].isChecked() is True
    assert view._venue_toggles[_FUTURES].isChecked() is False


def test_a_legacy_scalar_config_shows_its_one_venue(
    qapp, request, credentials_provider
):
    config = _FakeConfig({_SCALAR: _FUTURES.value})
    presenter, _view = _presenter(request, config, _Sessions(), credentials_provider)

    assert presenter._settings_view_model.enabledVenues == [_FUTURES.value]


def test_an_unreadable_saved_value_shows_trading_off(
    qapp, request, credentials_provider
):
    """`resolve_trading_venues` enables nothing for a value it cannot parse,
    never the tradeable one. The screen shows that, since that is what the
    app booted with."""
    config = _FakeConfig({_SCALAR: "mainnet_please"})
    presenter, _view = _presenter(request, config, _Sessions(), credentials_provider)

    assert presenter._settings_view_model.enabledVenues == []


def test_ticking_a_toggle_reaches_the_view_model(qapp, request, credentials_provider):
    presenter, view = _presenter(
        request, _FakeConfig(), _Sessions(), credentials_provider
    )

    view._venue_toggles[_SPOT].setChecked(True)

    assert presenter._settings_view_model.enabledVenues == [_SPOT.value]


def test_saving_writes_the_list_in_venue_order_and_keeps_the_scalar_in_step(
    qapp, request, credentials_provider
):
    """Ticked Spot first, then Futures: the list follows `TradingVenue`'s own
    order, so which venue is primary never depends on the click order."""
    config = _FakeConfig({_SCALAR: "disabled"})
    presenter, _view = _presenter(request, config, _Sessions(), credentials_provider)
    view_model = presenter._settings_view_model
    view_model.requestVenueEnabled(_SPOT.value, True)
    view_model.requestVenueEnabled(_FUTURES.value, True)

    presenter.apply()

    assert config.values[_LIST] == [_FUTURES.value, _SPOT.value]
    assert config.values[_SCALAR] == _FUTURES.value
    assert view_model.statusIsError is False


def test_unticking_every_venue_saves_trading_off(qapp, request, credentials_provider):
    config = _FakeConfig({_LIST: [_SPOT.value]})
    presenter, _view = _presenter(request, config, _Sessions(), credentials_provider)
    view_model = presenter._settings_view_model
    view_model.requestVenueEnabled(_SPOT.value, False)

    presenter.apply()

    assert config.values[_LIST] == []
    assert config.values[_SCALAR] == TradingVenue.DISABLED.value


def test_saving_is_refused_while_any_venue_is_trading(
    qapp, request, credentials_provider
):
    """Only Spot's session is live, and the primary venue's is not: the lock
    still holds. Refused, not partially applied."""
    config = _FakeConfig({_LIST: [_FUTURES.value, _SPOT.value]})
    sessions = _Sessions()
    notifier = RecordingNotifier()
    presenter, _view = _presenter(
        request, config, sessions, credentials_provider, notifier
    )
    sessions.spot.set_enabled(enabled=True)
    view_model = presenter._settings_view_model
    view_model.requestVenueEnabled(_SPOT.value, False)

    presenter.apply()

    assert config.values[_LIST] == [_FUTURES.value, _SPOT.value]
    (notice,) = notifier.failures
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == "trading.settings.save"
    assert "Trading is active" in notice.headline


def test_the_toggles_are_disabled_while_trading_is_on(
    qapp, request, credentials_provider
):
    sessions = _Sessions()
    sessions.spot.set_enabled(enabled=True)

    _presenter_obj, view = _presenter(
        request, _FakeConfig({_LIST: [_SPOT.value]}), sessions, credentials_provider
    )

    assert not any(toggle.isEnabled() for toggle in view._venue_toggles.values())
    # `isVisible()` is False for any widget whose window was never shown,
    # so the meaningful assertion is that the explanation was set at all.
    assert view._venue_lock_label.text() != ""


def test_turning_one_venue_off_leaves_the_other_served_after_restart(
    qapp, request, credentials_provider
):
    """What Settings saves is what the next boot serves: with Spot unticked,
    the real registry enables Futures alone and refuses Spot."""
    config = _FakeConfig({_LIST: [_FUTURES.value, _SPOT.value]})
    presenter, _view = _presenter(request, config, _Sessions(), credentials_provider)
    presenter._settings_view_model.requestVenueEnabled(_SPOT.value, False)
    presenter.apply()

    container = StdLibContainer()
    container.singleton(IConfig, DictConfig(config.get_all()))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    bind_state(container)
    contexts = container.resolve(IVenueContexts)

    assert contexts.enabled() == (_FUTURES,)
    assert contexts.primary().venue is _FUTURES


def test_a_venue_change_that_cannot_be_written_is_taken_back(
    qapp, request, credentials_provider, monkeypatch
):
    """PR #348 review: when `user_config.json` cannot be written, the live
    config must not keep the new venue list, or the next read of it routes
    as if the change had been saved. The edit stays on the page, dirty."""

    def refuse(_self) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(ConfigManager, "save", refuse)
    config = ConfigManager()
    config.load_dict({_LIST: [_FUTURES.value, _SPOT.value], _SCALAR: _FUTURES.value})
    notifier = RecordingNotifier()
    presenter, _view = _presenter(
        request, config, _Sessions(), credentials_provider, notifier
    )
    presenter._settings_view_model.requestVenueEnabled(_SPOT.value, False)

    presenter.apply()

    assert config.get(_LIST) == [_FUTURES.value, _SPOT.value]
    assert config.get(_SCALAR) == _FUTURES.value
    assert presenter.is_dirty()
    (notice,) = notifier.failures
    assert notice.kind is FailureKind.COMMAND
    assert "venues were not changed" in notice.headline
    assert notice.detail == "read-only file system"
    assert "read-only" not in notice.headline


def test_a_secret_that_cannot_be_written_is_told_in_a_box_and_changes_nothing(
    qapp, request, credentials_provider
):
    credentials_provider.save_to_file.side_effect = OSError("disk full")
    config = _FakeConfig({_LIST: [_FUTURES.value]})
    notifier = RecordingNotifier()
    presenter, _view = _presenter(
        request, config, _Sessions(), credentials_provider, notifier
    )
    presenter._settings_view_model.apiKey = "k"

    presenter.apply()

    (notice,) = notifier.failures
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == "trading.settings.save"
    assert "secrets.local.json" in notice.headline
    assert notice.detail == "disk full"
    assert "disk full" not in notice.headline


def test_a_key_already_written_stays_saved_when_the_venues_cannot_be(
    qapp, request, tmp_path, monkeypatch
):
    """PR #348 re-review (S1), the second branch: the secrets file is written
    first, so when `user_config.json` then fails, the new key is saved and
    the page takes it as saved; only the venue change stays unapplied."""
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_SECRET", raising=False)

    def refuse(_self) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(ConfigManager, "save", refuse)
    secrets = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    secrets.write("old-key", "old-secret")
    provider = EnvFirstCredentialsProvider(secrets, _FUTURES)
    config = ConfigManager()
    config.load_dict({_LIST: [_FUTURES.value, _SPOT.value], _SCALAR: _FUTURES.value})
    presenter, _view = _presenter(request, config, _Sessions(), provider)
    view_model = presenter._settings_view_model
    view_model.apiKey = "new-key"
    view_model.requestVenueEnabled(_SPOT.value, False)

    presenter.apply()

    saved = provider.resolve().credentials
    assert saved is not None
    assert saved.api_key == "new-key"
    assert config.get(_LIST) == [_FUTURES.value, _SPOT.value]
    assert presenter._saved_fields[0] == "new-key"
    assert presenter.is_dirty()
