"""`BOT-125` — the Data Source (chart) venue control on the Market Data
settings section.

Split off `tests/unit/presentation/ui/screens/test_settings_venue_controls.py`
(`EPIC-025E` PR 4.4e), keeping only what this module owns. `trading`'s
venue kept its lock and moved to
`tests/unit/modules/trading/ui/settings/test_trading_settings_venue.py`.

**No lock here — a deliberate finding, not a regression.** The old monolith
disabled this combo too while trading was on, under one shared flag read
from `ITradingSession`. That flag cannot follow this field into
`market_data`: `trading.dependencies` already names `["market_data"]`
(`modules/trading/module.py`), so `market_data` reading `ITradingSession`
back would be the exact import cycle `ExtensionCircularDependencyError`
caught on PR 4.4c's first attempt. This venue only selects which venue's
candles a chart reads — not order routing — so the lock's own reasoning
never applied here as urgently as it does to Trading's own venue. See
`MarketDataSettingsPresenter`'s module docstring for the full argument.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_presenter import (
    MarketDataSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_view import (
    MarketDataSettingsView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.interfaces import IConfig


class _FakeConfig:
    """Stores what it is given, so the assertions can be about values
    rather than about `set` having been called with something."""

    def __init__(self, initial: dict | None = None) -> None:
        self.values: dict = {
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


def _presenter(request, config):
    container = Mock()
    container.resolve.side_effect = lambda interface: (
        config
        if interface is IConfig or getattr(interface, "__name__", "") == "IConfig"
        else Mock()
    )
    view = MarketDataSettingsView()
    request.addfinalizer(view.deleteLater)
    return MarketDataSettingsPresenter(view, container), view


def test_every_market_data_venue_has_a_combo_label(qapp, request):
    """A member added without a label would render as an empty combo row."""
    _presenter_obj, view = _presenter(request, _FakeConfig())

    labels = {
        view._market_data_venue_combo.itemText(index)
        for index in range(view._market_data_venue_combo.count())
    }

    assert len(labels) == len(MarketDataVenue)
    assert all(label.strip() for label in labels)


def test_the_saved_venue_is_shown_on_load(qapp, request):
    config = _FakeConfig(
        {ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: "futures_testnet"}
    )
    presenter, _view = _presenter(request, config)

    assert presenter._settings_view_model.marketDataVenue == "futures_testnet"


def test_an_unreadable_saved_value_shows_what_is_actually_running(qapp, request):
    """`resolve_market_data_venue` falls back to a known member for a value
    it cannot parse. The screen must show that fallback, since that is what
    the app booted with; echoing the broken string would misrepresent what
    is actually running."""
    config = _FakeConfig({ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value: "typo_venue"})
    presenter, _view = _presenter(request, config)

    assert presenter._settings_view_model.marketDataVenue in {
        venue.value for venue in MarketDataVenue
    }


def test_saving_writes_the_venue_key(qapp, request):
    config = _FakeConfig()
    presenter, _view = _presenter(request, config)
    view_model = presenter._settings_view_model
    view_model.requestMarketDataVenue("mainnet_public")

    view_model.requestSave()

    assert (
        config.values[ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value] == "mainnet_public"
    )


def test_the_combo_stays_enabled_while_trading_is_on(qapp, request):
    """The finding this file documents: unlike Trading's own venue, this
    combo has no lock at all — there is nothing here for a live trading
    session to disable."""
    _presenter_obj, view = _presenter(request, _FakeConfig())

    assert view._market_data_venue_combo.isEnabled() is True


def test_the_combo_carries_the_config_value_not_the_label(qapp, request):
    """The visible text is a human-readable sentence; the value written to
    config must be the enum's own string."""
    _presenter_obj, view = _presenter(request, _FakeConfig())

    values = {
        view._market_data_venue_combo.itemData(index)
        for index in range(view._market_data_venue_combo.count())
    }

    assert values == {venue.value for venue in MarketDataVenue}
