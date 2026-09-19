"""`BUG-117` follow-up — the Positions table's refresh interval is
configurable (`ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS`), but
clamped to a floor derived from Binance's documented request-weight budget
(`TradingModule._MIN_POSITION_REFRESH_INTERVAL_SECONDS`'s own comment) — a
misconfigured near-zero value must not spend that budget on nothing else.

`EPIC-025E` PR 4.4f-4 moved this test alongside its subject: the static
method and its two module constants moved from `binance_bot_module.py` into
`modules/trading/module.py`, and so did this file.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.module import (
    _DEFAULT_POSITION_REFRESH_INTERVAL_SECONDS,
    _MIN_POSITION_REFRESH_INTERVAL_SECONDS,
    TradingModule,
)


def _config(value: object = None) -> MagicMock:
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: (
        value if value is not None else default
    )
    return config


def test_no_config_value_falls_back_to_the_documented_default():
    interval = TradingModule._position_refresh_interval_seconds(_config())

    assert interval == _DEFAULT_POSITION_REFRESH_INTERVAL_SECONDS


def test_a_configured_value_above_the_floor_is_honored():
    interval = TradingModule._position_refresh_interval_seconds(_config(10.0))

    assert interval == 10.0


def test_a_configured_value_below_the_floor_is_clamped_up():
    interval = TradingModule._position_refresh_interval_seconds(_config(0.1))

    assert interval == _MIN_POSITION_REFRESH_INTERVAL_SECONDS


def test_clamping_logs_a_warning_naming_the_key_and_the_floor(caplog):
    with caplog.at_level(logging.WARNING, logger="App.TradingModule"):
        TradingModule._position_refresh_interval_seconds(_config(0.0))

    assert any(
        ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS.value
        in record.getMessage()
        for record in caplog.records
    )
