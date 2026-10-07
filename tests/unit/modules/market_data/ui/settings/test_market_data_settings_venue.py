"""The Data Source option is gone from the Market Data settings section.

@details A screen with no trading venue always reads the public mainnet
(`DEFAULT_MARKET_DATA_VENUE`) and every venue screen its own venue's market
(`BUG-172`), so Tools -> Options -> Market Data offers no Data Source and an
Apply writes no `exchange.market_data_venue`. A `user_config.json` that still
holds the key is left as it is: nothing on this page reads or rewrites it.
"""

from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtWidgets import QComboBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_presenter import (
    MarketDataSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_view import (
    MarketDataSettingsView,
)
from sagittarius_engine.interfaces import IConfig

_RETIRED_KEY = "exchange.market_data_venue"


class _FakeConfig:
    """Stores what it is given, so the assertions can be about values."""

    def __init__(self, initial: dict | None = None) -> None:
        self.values: dict = {
            "DEFAULT_SYMBOLS": ["BTCUSDT"],
            "DEFAULT_INTERVAL": "1m",
            "DEFAULT_SYNC_DAYS": 1,
        }
        self.values.update(initial or {})

    def get(self, key, default=None, cast=None):
        return self.values.get(key, default)

    def get_all(self):
        return dict(self.values)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        pass


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


def test_the_page_offers_no_data_source(qapp, request):
    _presenter_obj, view = _presenter(request, _FakeConfig())

    assert view.findChildren(QComboBox) == []
    assert not any("Data Source" in label.text() for label in view.findChildren(QLabel))


def test_applying_writes_no_data_source_key(qapp, request):
    config = _FakeConfig()
    presenter, _view = _presenter(request, config)

    presenter.apply()

    assert _RETIRED_KEY not in config.values


def test_a_leftover_data_source_key_is_neither_read_nor_rewritten(qapp, request):
    config = _FakeConfig({_RETIRED_KEY: "futures_testnet"})
    presenter, _view = _presenter(request, config)

    presenter.apply()

    assert config.values[_RETIRED_KEY] == "futures_testnet"
