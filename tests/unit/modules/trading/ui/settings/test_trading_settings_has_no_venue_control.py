"""`EPIC-034B` — the Trading page of Tools → Options has no venue control and
promises no restart: every venue with a usable key is on.

@details What the page used to do (a check box per venue, a lock while a
session ran, a list written to `user_config.json`) is gone; these tests hold
the page to the remainder: credentials in, a connection check out, and a
configuration that still names venues loading without effect.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QCheckBox, QLabel
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
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
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.interfaces import IConfig

_LEGACY_LIST = ConfigKeys.EXCHANGE_TRADING_VENUES.value
_LEGACY_SCALAR = ConfigKeys.EXCHANGE_TRADING_VENUE.value


def _presenter(request, config, provider):
    container = Mock()

    def resolve(interface):
        if interface is IConfig or getattr(interface, "__name__", "") == "IConfig":
            return config
        if interface is IVenueContexts:
            return primary_venue_contexts(provider)
        if interface is IAccountSnapshot:
            return FakeAccountSnapshot()
        return Mock()

    container.resolve.side_effect = resolve
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)
    return TradingSettingsPresenter(view, container), view


@pytest.fixture
def no_key_provider() -> Mock:
    provider = Mock(spec=IExchangeCredentialsProvider)
    provider.resolve.return_value = ResolvedCredentials(None, CredentialsSource.NONE)
    return provider


def test_the_page_has_no_venue_control(qapp, request, no_key_provider):
    _presenter_obj, view = _presenter(request, DictConfig(), no_key_provider)

    boxes = {box.objectName() for box in view.findChildren(QCheckBox)}

    assert not any(name.startswith("chkTradingVenue") for name in boxes)
    assert not hasattr(view, "_venue_toggles")


def test_the_page_does_not_say_a_key_needs_a_restart(qapp, request, no_key_provider):
    _presenter_obj, view = _presenter(request, DictConfig(), no_key_provider)

    text = " ".join(label.text() for label in view.findChildren(QLabel)).lower()

    assert "restart" not in text


@pytest.mark.parametrize(
    "values",
    [
        {},
        {_LEGACY_LIST: ["spot_testnet"]},
        {_LEGACY_LIST: []},
        {_LEGACY_SCALAR: TradingVenue.FUTURES_TESTNET.value},
        {_LEGACY_SCALAR: "mainnet_please"},
    ],
)
def test_a_configuration_that_names_venues_loads_and_is_not_dirty(
    qapp, request, no_key_provider, values
):
    presenter, _view = _presenter(request, DictConfig(values), no_key_provider)

    assert presenter.is_dirty() is False
    assert presenter.validation_message() is None


def test_saving_a_key_writes_the_secrets_file_and_no_venue_setting(
    qapp, request, tmp_path, monkeypatch
):
    """The key reaches the file the readers resolve from on every call, and
    nothing about venues is written."""
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_SECRET", raising=False)
    config = DictConfig({})
    provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "secrets.local.json")),
        TradingVenue.FUTURES_TESTNET,
    )
    presenter, _view = _presenter(request, config, provider)
    presenter._settings_view_model.apiKey = "new-key"
    presenter._settings_view_model.apiSecret = "new-secret"

    presenter.apply()

    saved = provider.resolve().credentials
    assert saved is not None
    assert (saved.api_key, saved.api_secret) == ("new-key", "new-secret")
    assert config.get(_LEGACY_LIST, None) is None
    assert presenter.is_dirty() is False
    assert "restart" not in presenter._settings_view_model.statusMessage.lower()
