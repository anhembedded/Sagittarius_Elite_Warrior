"""`BOT-125` review — the one place `LiveStrategyConfig` meets configuration.

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

@par One configuration per venue (`EPIC-028C`)
Futures and Spot each arm their own strategy, so each keeps its own six
keys: `trading.<venue>.live_symbol` and so on (`venue_config_key`). Arming on
one venue saves that venue's keys only and never replaces what the other
restores at boot.

The unscoped `trading.live_*` keys are what a single-venue app wrote. They
belong to the one venue that app ran on, which can be named for certain only
while exactly one venue is enabled: with trading off there is no owner yet,
and with two enabled the primary venue is not necessarily the one the keys
were armed on (the PR #295 review: a Spot strategy would move to Futures).
`adopt_legacy()` copies them to that one venue's own keys and then empties the
legacy strategy key, so a venue enabled later never inherits a strategy armed
on another market. In every other case it leaves the keys where they are and
says so.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    DEFAULT_LEVERAGE,
    DEFAULT_SIZING_PERCENT,
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.LiveStrategyConfigStore")

_SECTION = "trading."

#: The six keys one armed strategy is saved under, in the unscoped form a
#: single-venue app wrote them.
_LIVE_KEYS: tuple[ConfigKeys, ...] = (
    ConfigKeys.TRADING_LIVE_STRATEGY_KEY,
    ConfigKeys.TRADING_LIVE_SYMBOL,
    ConfigKeys.TRADING_LIVE_INTERVAL,
    ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS,
    ConfigKeys.TRADING_LIVE_SIZING_PERCENT,
    ConfigKeys.TRADING_LIVE_LEVERAGE,
)


def venue_config_key(key: ConfigKeys, venue: TradingVenue) -> str:
    """`trading.live_symbol` for Futures Testnet is
    `trading.futures_testnet.live_symbol`."""
    return f"{_SECTION}{venue.value}.{key.value.removeprefix(_SECTION)}"


class LiveStrategyConfigStore:
    """@brief Reads and writes each venue's armed strategy keys.

    @details Through the application's own two configuration ports, never the
    Engine's `IConfig`: an application service may import nothing from the
    Engine but the Shared Kernel (`architecture-rule.md` §3,
    `test_module_inside_imports_only_the_shared_kernel.py`). Both ports wrap
    the same configuration in the running app, so a value `set()` here is what
    the next `get()` reads.
    """

    def __init__(self, reader: IConfigReader, writer: IConfigWriter) -> None:
        self._reader = reader
        self._writer = writer

    def adopt_legacy(self, enabled: tuple[TradingVenue, ...]) -> None:
        """Moves a single-venue app's unscoped keys to the one enabled
        venue's own keys, once.

        Does nothing when no strategy was saved there, when the owner already
        has its own (a later boot, or a venue armed since), or when the owner
        cannot be named because not exactly one venue is enabled. The legacy
        strategy key is emptied after a move, which is what makes a second
        call a no-op.
        """
        legacy_strategy = self._reader.get(
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value, ""
        )
        if not legacy_strategy:
            return
        if not enabled:
            logger.debug(
                "Trading is off, so the saved live strategy '%s' has no venue "
                "to move to yet.",
                legacy_strategy,
            )
            return
        if len(enabled) > 1:
            logger.warning(
                "The saved live strategy '%s' predates per-venue settings and "
                "%d venues are enabled, so which one it belongs to is unknown "
                "— left unadopted; arm it again on the venue you want.",
                legacy_strategy,
                len(enabled),
            )
            return
        (owner,) = enabled
        owned = self._reader.get(
            venue_config_key(ConfigKeys.TRADING_LIVE_STRATEGY_KEY, owner)
        )
        if owned is not None:
            return
        for key in _LIVE_KEYS:
            value = self._reader.get(key.value)
            if value is not None:
                self._writer.set(venue_config_key(key, owner), value)
        self._writer.set(ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value, "")
        self._persist()
        logger.info(
            "Moved the saved live strategy '%s' to %s's own keys.",
            legacy_strategy,
            owner.value,
        )

    def load(self, venue: TradingVenue) -> LiveStrategyConfig:
        """@returns Whatever is saved for `venue`, as a value object; an
        incomplete one (`is_complete` false) when nothing is.

        @raises ValueError If the saved values break `LiveStrategyConfig`'s
        own invariants (a leverage of 0, an interval live trading does not
        support). Deliberately propagated rather than corrected here: the
        callers want different recoveries — the saved-selection port restores
        "nothing selected", an arm shows it as a refusal — and a store that
        quietly substituted a "safe" value would hide a config the user
        believes is in effect.
        """
        return LiveStrategyConfig(
            strategy_key=self._text(ConfigKeys.TRADING_LIVE_STRATEGY_KEY, venue),
            symbol=self._text(ConfigKeys.TRADING_LIVE_SYMBOL, venue),
            interval=self._text(ConfigKeys.TRADING_LIVE_INTERVAL, venue),
            strategy_params=self._params(venue),
            sizing_percent=self._number(
                venue_config_key(ConfigKeys.TRADING_LIVE_SIZING_PERCENT, venue),
                DEFAULT_SIZING_PERCENT,
            ),
            leverage=self._number(
                venue_config_key(ConfigKeys.TRADING_LIVE_LEVERAGE, venue),
                DEFAULT_LEVERAGE,
            ),
        )

    def save(self, venue: TradingVenue, config: LiveStrategyConfig) -> None:
        """Writes every field of `venue`'s keys, then persists."""
        values: dict[ConfigKeys, object] = {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY: config.strategy_key,
            ConfigKeys.TRADING_LIVE_SYMBOL: config.symbol,
            ConfigKeys.TRADING_LIVE_INTERVAL: config.interval,
            ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS: json.dumps(
                dict(config.strategy_params), sort_keys=True
            ),
            ConfigKeys.TRADING_LIVE_SIZING_PERCENT: config.sizing_percent,
            ConfigKeys.TRADING_LIVE_LEVERAGE: config.leverage,
        }
        for key, value in values.items():
            self._writer.set(venue_config_key(key, venue), value)
        self._persist()

    # ------------------------------------------------------------------ #

    def _persist(self) -> None:
        """Writes everything `set()` recorded to disk (`IConfigWriter.save`)."""
        self._writer.save()

    def _text(self, key: ConfigKeys, venue: TradingVenue) -> str:
        return str(self._reader.get(venue_config_key(key, venue), ""))

    def _number(self, key: str, fallback: float) -> float:
        """@details A non-numeric saved value falls back rather than
        raising: unlike an out-of-range number (which the user chose and
        should be told about), a `"twenty"` where a float belongs is a
        corrupt file, and refusing to boot over it helps nobody."""
        try:
            return float(self._reader.get(key, fallback))
        except (TypeError, ValueError):
            logger.warning(
                "Value for %s is not a number — using default %s.", key, fallback
            )
            return float(fallback)

    def _params(self, venue: TradingVenue) -> dict[str, Any]:
        raw = self._text(ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS, venue)
        if not raw:
            return {}
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Skipping %s — could not parse JSON.",
                venue_config_key(ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS, venue),
            )
            return {}
        return stored if isinstance(stored, dict) else {}
