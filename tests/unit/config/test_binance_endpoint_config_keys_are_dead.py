"""Regression test for `BUG-081` — `BINANCE_REST_URL`/`BINANCE_WS_URL` were
declared in `ConfigKeys` and `app_config.json` but read nowhere in `src/`, so
editing them changed nothing. Written before the fix, per `bug-fix-rule.md`:
confirmed failing (both keys present) on the code as `EPIC-021A` found it.

Not a blanket "every `ConfigKeys` member must be referenced" scanner — this
repo's `log.*` keys are genuinely consumed too, just as literal strings
passed straight through to the engine's config layer rather than via
`ConfigKeys.X` attribute access (see `app_bootstrapper.py`'s
`"log.level": verbosity.log_level`). A scanner grepping for attribute
references alone would flag those as false positives. This test instead
proves the two specific dead keys are gone, and that their replacement (the
venue config) is genuinely wired into the composition root — the same
mistake would not have shipped a second time undetected.
"""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys

_SRC_DIR = Path(__file__).resolve().parents[3] / "src"
_CONFIG_DIR = _SRC_DIR / "config"
_MODULE_SOURCE = (_SRC_DIR / "binance_bot_module.py").read_text(encoding="utf-8")
_ENDPOINTS_SOURCE = (
    _SRC_DIR / "infrastructure" / "binance" / "binance_endpoints.py"
).read_text(encoding="utf-8")


def test_dead_endpoint_keys_removed_from_config_keys_enum() -> None:
    member_names = {member.name for member in ConfigKeys}
    assert "BINANCE_REST_URL" not in member_names
    assert "BINANCE_WS_URL" not in member_names


def test_dead_endpoint_keys_removed_from_app_config_json() -> None:
    app_config = json.loads((_CONFIG_DIR / "app_config.json").read_text())
    assert "BINANCE_REST_URL" not in app_config
    assert "BINANCE_WS_URL" not in app_config


def test_market_data_venue_key_is_actually_read_by_composition_root() -> None:
    """The replacement must not repeat `BUG-081` — declared but unread.

    Checks the real call chain from the composition root rather than one
    file's raw text: `binance_bot_module.py` calls `resolve_market_data_venue`,
    and that function's own source is what actually reads the config key.
    """
    assert "resolve_market_data_venue" in _MODULE_SOURCE
    assert "ConfigKeys.EXCHANGE_MARKET_DATA_VENUE" in _ENDPOINTS_SOURCE
