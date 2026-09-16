"""`BOT-125` review — the one place `LiveStrategyConfig` meets `IConfig`.

@details `EPIC-022` shipped this mapping twice: `binance_bot_module.
_arm_from_config()` read the six `trading.live_*` keys to arm at boot, and
`StrategyArmingCoordinator` read the same six to fill the strategy card
and wrote them back on a successful arm. Same keys, same JSON blob, same
fallbacks — two copies, already differing in small ways (only one logged
the unreadable-JSON case), and free to drift further apart the moment a
seventh key appears.

One store, both callers. Loading and saving are inverse operations on the
same key set, so they belong to one object rather than to whichever screen
happened to need them first.

@par Why an application service and not a Presenter helper
Boot has no Presenter. Putting this in `screens/trading/` would mean
`binance_bot_module.py` importing a UI package to start the bot, which is
the layering inversion `EPIC-021L` spent a whole task removing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    DEFAULT_LEVERAGE,
    DEFAULT_SIZING_PERCENT,
    LiveStrategyConfig,
)
from sagittarius_engine.interfaces.i_config import IConfig

logger = logging.getLogger("App.LiveStrategyConfigStore")


class LiveStrategyConfigStore:
    """@brief Reads and writes the live strategy's `trading.live_*` keys."""

    def __init__(self, config: IConfig) -> None:
        self._config = config

    def load(self) -> LiveStrategyConfig:
        """@returns Whatever is saved, as a value object.

        @raises ValueError If the saved values break `LiveStrategyConfig`'s
        own invariants (a leverage of 0, an interval live trading does not
        support). Deliberately propagated rather than corrected here: the
        two callers want different recoveries — boot logs it and starts
        disarmed, the screen shows it as a refusal — and a store that
        quietly substituted a "safe" value would hide a config the user
        believes is in effect.
        """
        return LiveStrategyConfig(
            strategy_key=self._text(ConfigKeys.TRADING_LIVE_STRATEGY_KEY),
            symbol=self._text(ConfigKeys.TRADING_LIVE_SYMBOL),
            interval=self._text(ConfigKeys.TRADING_LIVE_INTERVAL),
            strategy_params=self._params(),
            sizing_percent=self._number(
                ConfigKeys.TRADING_LIVE_SIZING_PERCENT, DEFAULT_SIZING_PERCENT
            ),
            leverage=self._number(ConfigKeys.TRADING_LIVE_LEVERAGE, DEFAULT_LEVERAGE),
        )

    def save(self, config: LiveStrategyConfig) -> None:
        """Writes every field, then persists if the config implementation
        can (`save()` belongs to `ConfigManager`, not to the `IConfig`
        port — the same duck-check `SettingsPresenter` documents)."""
        self._config.set(
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value, config.strategy_key
        )
        self._config.set(ConfigKeys.TRADING_LIVE_SYMBOL.value, config.symbol)
        self._config.set(ConfigKeys.TRADING_LIVE_INTERVAL.value, config.interval)
        self._config.set(
            ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS.value,
            json.dumps(dict(config.strategy_params), sort_keys=True),
        )
        self._config.set(
            ConfigKeys.TRADING_LIVE_SIZING_PERCENT.value, config.sizing_percent
        )
        self._config.set(ConfigKeys.TRADING_LIVE_LEVERAGE.value, config.leverage)
        persist = getattr(self._config, "save", None)
        if callable(persist):
            persist()

    # ------------------------------------------------------------------ #

    def _text(self, key: ConfigKeys) -> str:
        return str(self._config.get(key.value, ""))

    def _number(self, key: ConfigKeys, fallback: float) -> float:
        """@details A non-numeric saved value falls back rather than
        raising: unlike an out-of-range number (which the user chose and
        should be told about), a `"twenty"` where a float belongs is a
        corrupt file, and refusing to boot over it helps nobody."""
        try:
            return float(self._config.get(key.value, fallback))
        except (TypeError, ValueError):
            logger.warning(
                "Value for %s is not a number — using default %s.", key.value, fallback
            )
            return float(fallback)

    def _params(self) -> dict[str, Any]:
        raw = self._text(ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS)
        if not raw:
            return {}
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Skipping %s — could not parse JSON.",
                ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS.value,
            )
            return {}
        return stored if isinstance(stored, dict) else {}
