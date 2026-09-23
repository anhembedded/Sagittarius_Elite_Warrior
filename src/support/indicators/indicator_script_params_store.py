"""`BOT-063` — the one place a Dev Board indicator script's saved
parameter values meet `IConfig`.

@details Mirrors `modules/strategy/application/services/
live_strategy_config_store.py`'s JSON-blob-via-IConfig shape, keyed by
script key instead of holding one strategy's fields directly — several
scripts can be enabled and independently edited at once, unlike the one
live strategy.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from sagittarius_engine.interfaces.i_config import IConfig

logger = logging.getLogger("App.IndicatorScriptParamsStore")


class IndicatorScriptParamsStore:
    """@brief Reads and writes every indicator script's saved params."""

    def __init__(self, config: IConfig) -> None:
        self._config = config

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Every script key that has a saved override, each mapped to its
        own params dict. A key with no saved override simply is not
        present — the caller falls back to that script's own declared
        defaults, the same "empty means every default" convention
        `TRADING_LIVE_STRATEGY_PARAMS` uses."""
        raw = str(
            self._config.get(ConfigKeys.DASHBOARD_INDICATOR_SCRIPT_PARAMS.value, "")
        )
        if not raw:
            return {}
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Skipping %s — could not parse JSON.",
                ConfigKeys.DASHBOARD_INDICATOR_SCRIPT_PARAMS.value,
            )
            return {}
        if not isinstance(stored, dict):
            return {}
        return {key: value for key, value in stored.items() if isinstance(value, dict)}

    def save(self, key: str, params: dict[str, Any]) -> None:
        """Read-modify-write: only `key`'s own entry changes, every other
        script's saved params are carried through untouched."""
        all_params = self.load_all()
        all_params[key] = dict(params)
        self._config.set(
            ConfigKeys.DASHBOARD_INDICATOR_SCRIPT_PARAMS.value,
            json.dumps(all_params, sort_keys=True),
        )
        persist = getattr(self._config, "save", None)
        if callable(persist):
            persist()
