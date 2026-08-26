"""`EPIC-010H` — the middle tier: Settings' `DEFAULT_*`, read one way.

@details Before this, only `BackTestPresenter` read those keys; the Dev Board
and Database screens ignored them, so editing Settings changed one screen out
of three with nothing to tell the user the others were not listening.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL,
    FALLBACK_SYMBOL_OPTIONS,
    default_interval,
    default_symbol,
    default_symbol_options,
)

_ALLOWED = ("1m", "5m", "1h")


def test_settings_wins_when_it_declares_a_symbol():
    assert default_symbol({"DEFAULT_SYMBOLS": ["SOLUSDT", "XRPUSDT"]}, "ETHUSDT") == (
        "SOLUSDT"
    )


def test_settings_wins_when_it_declares_an_interval():
    assert default_interval({"DEFAULT_INTERVAL": "5m"}, "1m", _ALLOWED) == "5m"


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"DEFAULT_SYMBOLS": []},
        {"DEFAULT_SYMBOLS": None},
        {"DEFAULT_SYMBOLS": "BTCUSDT"},  # a string, not a list
        {"DEFAULT_SYMBOLS": ["", "   "]},
        {"DEFAULT_SYMBOLS": [1, 2]},
    ],
    ids=["absent", "empty", "null", "not-a-list", "blank", "wrong-type"],
)
def test_an_unusable_symbol_setting_falls_back(config):
    assert default_symbol(config, "ETHUSDT") == "ETHUSDT"


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"DEFAULT_INTERVAL": ""},
        {"DEFAULT_INTERVAL": "   "},
        {"DEFAULT_INTERVAL": None},
        {"DEFAULT_INTERVAL": 5},
        {"DEFAULT_INTERVAL": "7q"},  # syntactically fine, not on offer
    ],
    ids=["absent", "empty", "blank", "null", "wrong-type", "not-offered"],
)
def test_an_unusable_interval_setting_falls_back(config):
    assert default_interval(config, "1m", _ALLOWED) == "1m"


def test_an_interval_the_picker_cannot_show_is_refused():
    """A screen whose timeframe picker offers a fixed set must not start on a
    value that picker has no entry for — the user would see a control whose
    displayed value does not match what the screen will actually run."""
    assert default_interval({"DEFAULT_INTERVAL": "1s"}, "1m", _ALLOWED) == "1m"


def test_without_an_allowed_set_any_configured_interval_is_taken():
    """The Dev Board's timeframe comes from a chart toolbar built later, so it
    has no list to check against at this point and must not invent one."""
    assert default_interval({"DEFAULT_INTERVAL": "1s"}, "1m") == "1s"


def test_symbol_options_fall_back_to_the_callers_own_list():
    assert default_symbol_options({}, FALLBACK_SYMBOL_OPTIONS) == list(
        FALLBACK_SYMBOL_OPTIONS
    )


def test_blank_entries_are_dropped_but_the_rest_survive():
    assert default_symbol_options(
        {"DEFAULT_SYMBOLS": ["BTCUSDT", "  ", "ETHUSDT"]}, ["FALLBACK"]
    ) == ["BTCUSDT", "ETHUSDT"]


def test_the_fallback_is_the_callers_and_never_a_shared_one():
    """The invariant this module set for itself, and then broke once: change
    *where* a default comes from, never *what it is* on an unconfigured
    install. An earlier draft owned one global fallback, which silently moved
    the Database screen's starting symbol off `BTCUSDT` — caught by that
    screen's own tests. Pinned here so it cannot come back.
    """
    assert default_symbol({}, "BTCUSDT") == "BTCUSDT"
    assert default_symbol({}, FALLBACK_SYMBOL) == FALLBACK_SYMBOL
    assert default_interval({}, "1s") == "1s"
    assert default_interval({}, FALLBACK_INTERVAL) == FALLBACK_INTERVAL
