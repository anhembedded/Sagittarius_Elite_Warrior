"""A `user_config.json` that still holds the retired Data Source key.

@details The key is ignored — it reaches only the one-off legacy-candle labelling —
and that is said once, at INFO. An absent key is the default install: silent.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.retired_data_source_setting import (
    RETIRED_KEY,
    retired_data_source_setting,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig


def test_a_leftover_key_is_returned_for_the_labelling_and_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="App.Database"):
        raw = retired_data_source_setting(DictConfig({RETIRED_KEY: "futures_testnet"}))

    assert raw == "futures_testnet"
    ignored = [r for r in caplog.records if "[retired-setting]" in r.getMessage()]
    assert len(ignored) == 1
    assert ignored[0].levelno == logging.INFO
    assert "futures_testnet" in ignored[0].getMessage()


def test_an_absent_key_is_none_and_silent(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="App.Database"):
        raw = retired_data_source_setting(DictConfig({}))

    assert raw is None
    assert caplog.records == []


def test_a_value_naming_no_venue_does_not_crash() -> None:
    assert retired_data_source_setting(DictConfig({RETIRED_KEY: 5})) == 5
