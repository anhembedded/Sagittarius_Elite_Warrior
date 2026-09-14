"""`BOT-125` — the two exchange-environment controls in Settings.

Before this, `exchange.market_data_venue` and `exchange.trading_venue` were
file-edit-and-restart config with no UI anywhere — a user who had just
configured a strategy still could not turn trading on without editing
`app_config.json` by hand. These tests hold the new controls to the two
things that make them honest: they refuse rather than half-apply while a
live session is running, and a broken saved value shows what the app is
really running on rather than the unusable string that produced it.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.venue_labels import (
    MARKET_DATA_VENUE_LABELS,
    TRADING_VENUE_LABELS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces import IConfig


class _FakeConfig:
    """Stores what it is given, so the assertions can be about values
    rather than about `set` having been called with something."""

    def __init__(self, initial: dict | None = None) -> None:
        self.values = {
            "DEFAULT_SYMBOLS": ["BTCUSDT"],
            "DEFAULT_INTERVAL": "1m",
            "DEFAULT_SYNC_DAYS": 1,
        }
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


@pytest.fixture
def credentials_provider() -> Mock:
    provider = Mock(spec=IExchangeCredentialsProvider)
    provider.resolve.return_value = ResolvedCredentials(None, CredentialsSource.NONE)
    return provider


def _presenter(qapp, request, config, session_state, credentials_provider):
    container = Mock()

    def resolve(interface):
        if interface is IConfig or getattr(interface, "__name__", "") == "IConfig":
            return config
        if interface is IExchangeCredentialsProvider:
            return credentials_provider
        if interface is TradingSessionState:
            return session_state
        return Mock()

    container.resolve.side_effect = resolve
    view = SettingsView()
    request.addfinalizer(view.deleteLater)
    return SettingsPresenter(view, container), view


def test_every_enum_member_has_a_vietnamese_label():
    """A member added without a label would render as an empty combo row —
    the guard exists because `TradingVenue` is explicitly designed to gain
    a `MAINNET` member one day (`EPIC-021` ADR §3)."""
    assert set(MARKET_DATA_VENUE_LABELS) == set(MarketDataVenue)
    assert set(TRADING_VENUE_LABELS) == set(TradingVenue)
    assert all(label.strip() for label in MARKET_DATA_VENUE_LABELS.values())
    assert all(label.strip() for label in TRADING_VENUE_LABELS.values())


def test_the_saved_venues_are_shown_on_load(qapp, request, credentials_provider):
    config = _FakeConfig(
        {
            ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: "futures_testnet",
            ConfigKeys.EXCHANGE_TRADING_VENUE.value: "futures_testnet",
        }
    )
    presenter, _view = _presenter(
        qapp, request, config, TradingSessionState(), credentials_provider
    )

    view_model = presenter._settings_view_model

    assert view_model.marketDataVenue == "futures_testnet"
    assert view_model.tradingVenue == "futures_testnet"


def test_an_unreadable_saved_value_shows_what_is_actually_running(
    qapp, request, credentials_provider
):
    """`resolve_trading_venue` falls back to DISABLED for a value it cannot
    parse — and never to the tradeable one. The screen must show that
    fallback, since that is what the app booted with; echoing the broken
    string would tell the user trading is configured when it is not."""
    config = _FakeConfig(
        {
            ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: "typo_venue",
            ConfigKeys.EXCHANGE_TRADING_VENUE.value: "mainnet_please",
        }
    )
    presenter, _view = _presenter(
        qapp, request, config, TradingSessionState(), credentials_provider
    )

    assert presenter._settings_view_model.tradingVenue == TradingVenue.DISABLED.value
    assert presenter._settings_view_model.marketDataVenue in {
        venue.value for venue in MarketDataVenue
    }


def test_saving_writes_both_venue_keys(qapp, request, credentials_provider):
    config = _FakeConfig()
    presenter, _view = _presenter(
        qapp, request, config, TradingSessionState(), credentials_provider
    )
    view_model = presenter._settings_view_model
    view_model.requestTradingVenue("futures_testnet")
    view_model.requestMarketDataVenue("mainnet_public")

    view_model.requestSave()

    assert config.values[ConfigKeys.EXCHANGE_TRADING_VENUE.value] == "futures_testnet"
    assert (
        config.values[ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value] == "mainnet_public"
    )
    # No `save_count` assertion: `SettingsPresenter` only calls `save()` on a
    # real `ConfigManager` (its own docstring says a substituted `IConfig`
    # "simply won't persist, which is the correct behaviour for those"), so
    # asserting it here would be asserting against a fake, not the app.


def test_saving_is_refused_outright_while_trading_is_on(
    qapp, request, credentials_provider
):
    """Refused, not partially applied: a Save that wrote the other fields
    and silently dropped these two is the "button appears to work" failure
    `EPIC-022` was opened to remove."""
    config = _FakeConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: "disabled"})
    session_state = TradingSessionState()
    presenter, _view = _presenter(
        qapp, request, config, session_state, credentials_provider
    )
    session_state.enable(set(), expected_generation=session_state.generation)
    view_model = presenter._settings_view_model
    view_model.requestTradingVenue("futures_testnet")

    view_model.requestSave()

    assert config.values[ConfigKeys.EXCHANGE_TRADING_VENUE.value] == "disabled"
    assert view_model.statusIsError is True
    assert "Trading is active" in view_model.statusMessage


def test_the_combos_are_disabled_while_trading_is_on(
    qapp, request, credentials_provider
):
    session_state = TradingSessionState()
    session_state.enable(set(), expected_generation=session_state.generation)

    _presenter_obj, view = _presenter(
        qapp, request, _FakeConfig(), session_state, credentials_provider
    )

    assert view._trading_venue_combo.isEnabled() is False
    assert view._market_data_venue_combo.isEnabled() is False
    # `isVisible()` is False for any widget whose window was never shown,
    # so the meaningful assertion is that the explanation was set at all.
    assert view._venue_lock_label.text() != ""


def test_the_combos_carry_the_config_value_not_the_label(
    qapp, request, credentials_provider
):
    """The visible text is a Vietnamese sentence; the value written to
    config must be the enum's own string. Deriving one from the other by
    parsing the label would break the moment the wording changes."""
    _presenter_obj, view = _presenter(
        qapp, request, _FakeConfig(), TradingSessionState(), credentials_provider
    )

    values = {
        view._trading_venue_combo.itemData(index)
        for index in range(view._trading_venue_combo.count())
    }

    assert values == {venue.value for venue in TradingVenue}
