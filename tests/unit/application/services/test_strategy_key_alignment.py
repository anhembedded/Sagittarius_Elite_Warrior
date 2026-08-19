"""
Guards the key alignment convention every BaseStrategy subclass must keep
(BOT-026): the indicator names `build_indicators()` declares must be exactly
the names `decide()` reads back out of `context.indicators`. A typo in either
place would otherwise only surface as a confusing runtime `KeyError` deep
inside a backtest/live run instead of failing a test.
"""

import ast
import textwrap
from inspect import getsource

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.multi_ema_trend_follower_strategy import (
    MultiEmaTrendFollowerStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.support_resistance_strategy import (
    SupportResistanceStrategy,
)


def _registry() -> StrategyRegistry:
    """Mirrors how `binance_bot_module.py` populates a StrategyRegistry —
    kept local rather than imported so this test doesn't depend on the DI
    module (and its PySide6/engine imports) just to enumerate strategies."""
    registry = StrategyRegistry()
    registry.register("ema_crossover", EmaCrossoverStrategy)
    registry.register("multi_ema_trend_follower", MultiEmaTrendFollowerStrategy)
    registry.register("support_resistance", SupportResistanceStrategy)
    return registry


def _indicator_keys_read_in_decide(strategy_cls: type) -> set[str]:
    """Static-analyses `decide()` for every `context.indicators[...]` read,
    resolving `self.SOME_KEY` class-constant subscripts back to their value
    so this doesn't need decide() to be actually run."""
    tree = ast.parse(textwrap.dedent(getsource(strategy_cls.decide)))
    keys: set[str] = set()
    for node in ast.walk(tree):
        is_indicators_subscript = (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "indicators"
        )
        if not is_indicators_subscript:
            continue
        key_node = node.slice
        if (
            isinstance(key_node, ast.Attribute)
            and isinstance(key_node.value, ast.Name)
            and key_node.value.id == "self"
        ):
            keys.add(getattr(strategy_cls, key_node.attr))
        elif isinstance(key_node, ast.Constant):
            keys.add(key_node.value)
    return keys


def test_build_indicators_keys_match_what_decide_reads():
    registry = _registry()

    for key, strategy_cls in registry.available().items():
        strategy = registry.create(key)
        declared = set(strategy.build_indicators().keys())
        used = _indicator_keys_read_in_decide(strategy_cls)

        assert declared == used, (
            f"{strategy_cls.__name__} ({key!r}): build_indicators() keys "
            f"{declared} do not match keys read via context.indicators in "
            f"decide() {used}"
        )
