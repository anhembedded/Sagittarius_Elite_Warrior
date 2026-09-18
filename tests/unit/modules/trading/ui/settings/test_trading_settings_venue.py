"""`BOT-125` — the Order Venue control on the Trading settings section.

Split off `tests/unit/presentation/ui/screens/test_settings_venue_controls.py`,
keeping only what this module owns: the trading venue, backed by this
module's own `ITradingSession`. `market_data`'s venue moved to
`tests/unit/modules/market_data/ui/settings/test_market_data_settings_venue.py`
and dropped the lock entirely (see that module's presenter docstring for why).

These tests hold the control to the two things that make it honest: it
refuses rather than half-applies while a live session is running, and a
broken saved value shows what the app is really running on rather than the
unusable string that produced it.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_presenter import (
    TradingSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view import (
    TradingSettingsView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces import IConfig


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


@pytest.fixture
def credentials_provider() -> Mock:
    provider = Mock(spec=IExchangeCredentialsProvider)
    provider.resolve.return_value = ResolvedCredentials(None, CredentialsSource.NONE)
    return provider


def _presenter(request, config, session_state, credentials_provider):
    container = Mock()

    def resolve(interface):
        if interface is IConfig or getattr(interface, "__name__", "") == "IConfig":
            return config
        if interface is IExchangeCredentialsProvider:
            return credentials_provider
        if interface is ITradingSession:
            return session_state
        if interface is IAccountSnapshot:
            return FakeAccountSnapshot()
        return Mock()

    container.resolve.side_effect = resolve
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)
    return TradingSettingsPresenter(view, container), view


def test_every_trading_venue_has_a_combo_label(qapp, request, credentials_provider):
    """A member added without a label would render as an empty combo row —
    the guard exists because `TradingVenue` is explicitly designed to gain
    a `MAINNET` member one day (`EPIC-021` ADR §3)."""
    _presenter_obj, view = _presenter(
        request, _FakeConfig(), FakeTradingSession(), credentials_provider
    )

    labels = {
        view._trading_venue_combo.itemText(index)
        for index in range(view._trading_venue_combo.count())
    }

    assert len(labels) == len(TradingVenue)
    assert all(label.strip() for label in labels)


def test_the_saved_venue_is_shown_on_load(qapp, request, credentials_provider):
    config = _FakeConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: "futures_testnet"})
    presenter, _view = _presenter(
        request, config, FakeTradingSession(), credentials_provider
    )

    assert presenter._settings_view_model.tradingVenue == "futures_testnet"


def test_an_unreadable_saved_value_shows_what_is_actually_running(
    qapp, request, credentials_provider
):
    """`resolve_trading_venue` falls back to DISABLED for a value it cannot
    parse — and never to the tradeable one. The screen must show that
    fallback, since that is what the app booted with; echoing the broken
    string would tell the user trading is configured when it is not."""
    config = _FakeConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: "mainnet_please"})
    presenter, _view = _presenter(
        request, config, FakeTradingSession(), credentials_provider
    )

    assert presenter._settings_view_model.tradingVenue == TradingVenue.DISABLED.value


def test_saving_writes_the_venue_key(qapp, request, credentials_provider):
    config = _FakeConfig()
    presenter, _view = _presenter(
        request, config, FakeTradingSession(), credentials_provider
    )
    view_model = presenter._settings_view_model
    view_model.requestTradingVenue("futures_testnet")

    view_model.requestSave()

    assert config.values[ConfigKeys.EXCHANGE_TRADING_VENUE.value] == "futures_testnet"


def test_saving_is_refused_outright_while_trading_is_on(
    qapp, request, credentials_provider
):
    """Refused, not partially applied: a Save that wrote the other fields
    and silently dropped this one would be the "button appears to work"
    failure `EPIC-022` was opened to remove."""
    config = _FakeConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: "disabled"})
    session_state = FakeTradingSession()
    presenter, _view = _presenter(request, config, session_state, credentials_provider)
    session_state.set_enabled(enabled=True)
    view_model = presenter._settings_view_model
    view_model.requestTradingVenue("futures_testnet")

    view_model.requestSave()

    assert config.values[ConfigKeys.EXCHANGE_TRADING_VENUE.value] == "disabled"
    assert view_model.statusIsError is True
    assert "Trading is active" in view_model.statusMessage


def test_the_combo_is_disabled_while_trading_is_on(qapp, request, credentials_provider):
    session_state = FakeTradingSession()
    session_state.set_enabled(enabled=True)

    _presenter_obj, view = _presenter(
        request, _FakeConfig(), session_state, credentials_provider
    )

    assert view._trading_venue_combo.isEnabled() is False
    # `isVisible()` is False for any widget whose window was never shown,
    # so the meaningful assertion is that the explanation was set at all.
    assert view._venue_lock_label.text() != ""


def test_the_combo_carries_the_config_value_not_the_label(
    qapp, request, credentials_provider
):
    """The visible text is a human-readable sentence; the value written to
    config must be the enum's own string. Deriving one from the other by
    parsing the label would break the moment the wording changes."""
    _presenter_obj, view = _presenter(
        request, _FakeConfig(), FakeTradingSession(), credentials_provider
    )

    values = {
        view._trading_venue_combo.itemData(index)
        for index in range(view._trading_venue_combo.count())
    }

    assert values == {venue.value for venue in TradingVenue}
