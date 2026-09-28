"""`EPIC-027N` AC3 — every strategy declares the `SignalAction`s it can
emit, and the declaration is proven against the strategy's own source, not
just its own say-so.

@details Path-scanning guard over `src/modules/strategy/domain/strategies/`
(registered in `scanned_roots_registry.py`, per `testing-rule.md` §2's own
requirement that every such guard fails on an empty scan). A strategy whose
`decide()` calls `self.short()`/`self.cover()` without declaring `SHORT`/
`COVER` in `supported_directions` would silently drop half of what it does
the moment it is armed on a Spot venue (`ArmStrategyCommandHandler` trusts
the declaration, never re-derives it) — the exact failure mode
`architecture-rule.md` §7.3 warns a prose-only decision invites.

Mutation-verified by hand: removing `SHORT` from `EmaTrendPullbackStrategy.
supported_directions` while its `decide()` still calls `self.short()` turns
this guard red for the right reason.

Retire when: `supported_directions` is generated from `decide()`'s own
static analysis rather than declared by hand — no such mechanism exists
today.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    BaseStrategy,
)


def _repo_root() -> Path:
    """By landmark, not by hop count (`test_no_root_is_found_by_counting.py`)."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()
_STRATEGIES_DIR = _REPO_ROOT / "src" / "modules" / "strategy" / "domain" / "strategies"
_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies"


def _registered_strategy_classes() -> list[type[BaseStrategy]]:
    """Every concrete `BaseStrategy` subclass defined in this directory's
    own `*_strategy.py` files — a real source scan, not a hand-copied list
    that could drift from `state_bindings.py`'s own registrations."""
    classes: list[type[BaseStrategy]] = []
    for path in sorted(_STRATEGIES_DIR.glob("*_strategy.py")):
        module = importlib.import_module(f"{_PACKAGE}.{path.stem}")
        for obj in vars(module).values():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
                and obj.__module__ == module.__name__
            ):
                classes.append(obj)
    return classes


_STRATEGY_CLASSES = _registered_strategy_classes()


def test_the_scan_itself_is_not_empty() -> None:
    assert _STRATEGY_CLASSES, (
        "no BaseStrategy subclass found under "
        f"{_STRATEGIES_DIR} — the scan's own root moved or emptied "
        "(scanned_roots_registry.py)."
    )


@pytest.mark.parametrize(
    "strategy_cls", _STRATEGY_CLASSES, ids=lambda cls: cls.__name__
)
def test_a_strategy_that_calls_short_declares_it(
    strategy_cls: type[BaseStrategy],
) -> None:
    source = inspect.getsource(strategy_cls)
    if "self.short(" in source:
        assert SignalAction.SHORT in strategy_cls.supported_directions, (
            f"{strategy_cls.__name__} calls self.short() but its "
            "supported_directions does not include SignalAction.SHORT — "
            "arming it on Spot would silently drop this signal instead of "
            "being refused (EPIC-027N AC2)."
        )


@pytest.mark.parametrize(
    "strategy_cls", _STRATEGY_CLASSES, ids=lambda cls: cls.__name__
)
def test_a_strategy_that_calls_cover_declares_it(
    strategy_cls: type[BaseStrategy],
) -> None:
    source = inspect.getsource(strategy_cls)
    if "self.cover(" in source:
        assert SignalAction.COVER in strategy_cls.supported_directions, (
            f"{strategy_cls.__name__} calls self.cover() but its "
            "supported_directions does not include SignalAction.COVER — "
            "arming it on Spot would silently drop this signal instead of "
            "being refused (EPIC-027N AC2)."
        )
