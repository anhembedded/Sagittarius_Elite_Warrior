"""`EPIC-028C` — each venue saves and restores its own armed strategy.

@details The engine's real `DictConfig` holds the values, so every assertion
reads what a restart would read.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    venue_config_key,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.live_config_ports import (
    DictConfigWriter,
    in_memory_config_store,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET

_FUTURES_CONFIG = LiveStrategyConfig(
    strategy_key="ema_crossover",
    symbol="BTCUSDT",
    interval="5m",
    strategy_params={"fast": 9},
    sizing_percent=10.0,
    leverage=3.0,
)
_SPOT_CONFIG = LiveStrategyConfig(
    strategy_key="rsi_reversion", symbol="ETHUSDT", interval="1h", leverage=1.0
)


def _legacy_config() -> DictConfig:
    """What a single-venue app saved: the unscoped `trading.live_*` keys."""
    return DictConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "ema_crossover",
            ConfigKeys.TRADING_LIVE_SYMBOL.value: "BTCUSDT",
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
            ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS.value: '{"fast": 9}',
            ConfigKeys.TRADING_LIVE_SIZING_PERCENT.value: 10.0,
            ConfigKeys.TRADING_LIVE_LEVERAGE.value: 3.0,
        }
    )


def test_a_venues_keys_are_named_after_it() -> None:
    assert (
        venue_config_key(ConfigKeys.TRADING_LIVE_SYMBOL, _FUTURES)
        == "trading.futures_testnet.live_symbol"
    )


def test_each_venue_restores_what_it_saved() -> None:
    store = in_memory_config_store(DictConfig())

    store.save(_FUTURES, _FUTURES_CONFIG)
    store.save(_SPOT, _SPOT_CONFIG)

    assert store.load(_FUTURES) == _FUTURES_CONFIG
    assert store.load(_SPOT) == _SPOT_CONFIG


def test_arming_on_one_venue_never_replaces_the_others_saved_strategy() -> None:
    store = in_memory_config_store(DictConfig())
    store.save(_FUTURES, _FUTURES_CONFIG)

    store.save(_SPOT, _SPOT_CONFIG)

    assert store.load(_FUTURES) == _FUTURES_CONFIG


def test_a_venue_that_saved_nothing_restores_nothing() -> None:
    store = in_memory_config_store(DictConfig())
    store.save(_FUTURES, _FUTURES_CONFIG)

    assert store.load(_SPOT).is_complete is False


def test_the_legacy_keys_become_the_one_enabled_venues_own() -> None:
    config = _legacy_config()
    store = in_memory_config_store(config)

    store.adopt_legacy((_FUTURES,))

    assert store.load(_FUTURES) == _FUTURES_CONFIG
    assert store.load(_SPOT).is_complete is False


def test_adopting_empties_the_legacy_strategy_so_it_happens_once() -> None:
    """A venue enabled later must never inherit a strategy armed on another
    market: once adopted, the legacy keys name no strategy."""
    config = _legacy_config()
    store = in_memory_config_store(config)
    store.adopt_legacy((_FUTURES,))

    store.adopt_legacy((_SPOT,))

    assert config.get(ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value) == ""
    assert store.load(_SPOT).is_complete is False


def test_adopting_never_overwrites_what_the_owner_saved_itself() -> None:
    config = _legacy_config()
    store = in_memory_config_store(config)
    armed_since = LiveStrategyConfig(
        strategy_key="rsi_reversion", symbol="SOLUSDT", interval="15m"
    )
    store.save(_FUTURES, armed_since)

    store.adopt_legacy((_FUTURES,))

    assert store.load(_FUTURES) == armed_since


def test_with_trading_off_the_legacy_keys_wait() -> None:
    """The PR #295 review's path: a first boot with trading off names no
    owner, so nothing moves and the keys are still there for a later boot."""
    config = _legacy_config()
    store = in_memory_config_store(config)

    store.adopt_legacy(())

    assert config.get(ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value) == "ema_crossover"
    assert store.load(_FUTURES).is_complete is False


def test_with_two_venues_enabled_the_owner_is_unknown_and_nothing_moves() -> None:
    """A strategy armed on Spot must not move to Futures just because
    Futures became the primary venue when Settings enabled both."""
    config = _legacy_config()
    store = in_memory_config_store(config)

    store.adopt_legacy((_FUTURES, _SPOT))

    assert store.load(_FUTURES).is_complete is False
    assert store.load(_SPOT).is_complete is False
    assert config.get(ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value) == "ema_crossover"


def test_a_disabled_first_boot_then_one_venue_adopts_on_that_venue() -> None:
    config = _legacy_config()
    store = in_memory_config_store(config)
    store.adopt_legacy(())

    store.adopt_legacy((_SPOT,))

    assert store.load(_SPOT) == _FUTURES_CONFIG


def test_saving_a_venue_persists_through_the_writer() -> None:
    """`EPIC-030D` — `save()` reaches disk through `IConfigWriter.save()`,
    the port's own method, not a `getattr(config, "save")` probe that a
    config without the method skipped silently."""
    config = DictConfig()
    writer = DictConfigWriter(config)
    store = in_memory_config_store(config, writer)

    store.save(_FUTURES, _FUTURES_CONFIG)

    assert writer.saves == 1


def test_adopting_the_legacy_keys_persists_through_the_writer() -> None:
    config = _legacy_config()
    writer = DictConfigWriter(config)
    store = in_memory_config_store(config, writer)

    store.adopt_legacy((_FUTURES,))

    assert writer.saves == 1
