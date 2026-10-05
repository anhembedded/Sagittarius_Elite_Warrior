"""`EPIC-033H` — the Market mode with three tracked symbols, one chart open
and the connection checked.

Offline: no container, no engine, no network. The view is filled directly:
Watchlist rows as ticks would leave them, sample hourly candles drawn on the
chart, and the status bar's two words.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    IndicatorChoice,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)

#: The package is `market`, a name another module's preview could share; the
#: key is explicit (`scripts/preview_qml.py`).
PREVIEW_KEY = "market_mode"
_START = datetime(2026, 9, 28, tzinfo=UTC)
_TICKS = (
    ("BTCUSDT", 64250.1, 1.25, 1532.4),
    ("ETHUSDT", 3120.55, -0.84, 20411.0),
    ("BNBUSDT", 581.2, 0.12, 8800.5),
)


def build_preview() -> QWidget:
    view = MarketView()
    view.watchlist.set_symbols([symbol for symbol, *_ in _TICKS])
    for symbol, price, change, volume in _TICKS:
        view.watchlist.update_tick(symbol, price, change, volume)
    view.set_indicator_choices(
        (
            IndicatorChoice("ema_20", "EMA 20", True),
            IndicatorChoice("rsi_14", "RSI 14", False),
            IndicatorChoice("macd", "MACD", False),
        )
    )
    card = ChartCard("BTCUSDT")
    candles = _sample_candles()
    card.render_historical_data(map_klines(candles))
    card.render_historical_volume(map_volume(candles))
    view.add_chart("BTCUSDT", card)
    view.set_connection_text("Exchange: connected (FUTURES_TESTNET)")
    view.set_stream_text("Market data: live")
    view.setWindowTitle("Market mode — sample")
    return view


def _sample_candles() -> list[MarketData]:
    candles = []
    price = 64000.0
    for hour in range(120):
        opened = _START + timedelta(hours=hour)
        close = price + 400 * math.sin(hour / 7) + 60 * math.cos(hour / 2)
        candles.append(
            MarketData(
                symbol="BTCUSDT",
                interval="1h",
                open_time=opened,
                open_price=price,
                high_price=max(price, close) + 80,
                low_price=min(price, close) - 80,
                close_price=close,
                volume=100 + 40 * abs(math.sin(hour)),
                close_time=opened + timedelta(hours=1),
                quote_asset_volume=0.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.0,
                taker_buy_quote_asset_volume=0.0,
            )
        )
        price = close
    return candles
