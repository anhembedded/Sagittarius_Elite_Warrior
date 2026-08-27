"""Which concrete Backtest View the app builds, decided once at bootstrap.

@details `EPIC-013F`. Two things were implicit here before:

1. **The choice was hardcoded.** `main_window.py` registered
   `lambda: BackTestView()`, so "which View" was a code edit rather than a
   named, configurable decision.
2. **The lambda had no type.** Nothing said what the router was allowed to
   do with whatever it returned — the same implicit contract
   `architecture-rule.md` §2.1 forbids, in factory form.

**Bootstrap-time, deliberately.** A View is chosen when the screen is
registered and never swapped while the app runs: `BackTestPresenter` is not
built to survive its View being replaced under it, and §2.1 records that as
a decision rather than an accident. This module is the one place that
decision is made, which is what keeps it from spreading.

**Not a plugin system.** There is exactly one View today, and the scope here
is *a named choice, read from config, returning a declared type* — nothing
more. This repo has a real precedent for the opposite: four stub cards
(`ActionCard`/`FormCard`/`StreamCard`/`TableCard`) inferred from a docstring,
zero real instances (`EPIC-006` ADR §4). Adding a second key is a few lines
when a second View actually exists.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from sagittarius_engine.interfaces.i_config import IConfig

from .backtest_view import BackTestView
from .ports.i_backtest_view import IBacktestView

logger = logging.getLogger("App.BacktestViewFactory")


class BacktestViewKey(str, Enum):
    """The Views this app knows how to build for the Backtest screen."""

    #: Plain `QtWidgets` throughout — the only View since `EPIC-006` removed
    #: QML from this app.
    QT_WIDGETS = "qtwidgets"


#: The choice when config says nothing, which is the normal case. Named
#: rather than repeated as a literal, per `code-quality-rule.md`.
DEFAULT_BACKTEST_VIEW_KEY = BacktestViewKey.QT_WIDGETS

#: Every key maps to a zero-argument builder returning something that
#: satisfies `IBacktestView`. A `dict` rather than an `if` chain so adding a
#: View is one entry, and so `resolve_backtest_view_key` can validate against
#: it without a second list to keep in sync.
_BUILDERS: dict[BacktestViewKey, Callable[[], IBacktestView]] = {
    BacktestViewKey.QT_WIDGETS: BackTestView,
}


def resolve_backtest_view_key(config: IConfig) -> BacktestViewKey:
    """The configured View key, or the default if it is missing or unusable.

    @details Warns on an unusable value instead of failing the boot: a typo
    in `user_config.json` should not leave the user with no app, and it must
    not be silent either — `logging-rule.md` §2 wants the branch that
    degraded to say what it chose and why.
    """
    raw = config.get(ConfigKeys.BACKTEST_VIEW.value, DEFAULT_BACKTEST_VIEW_KEY.value)
    try:
        return BacktestViewKey(raw)
    except ValueError:
        logger.warning(
            "Backtest view %r is not a known view; using %r. Known views: %s.",
            raw,
            DEFAULT_BACKTEST_VIEW_KEY.value,
            [key.value for key in _BUILDERS],
        )
        return DEFAULT_BACKTEST_VIEW_KEY


def build_backtest_view(config: IConfig) -> IBacktestView:
    """Construct the Backtest View this install is configured for.

    @details Logs which View was built, once per construction. That line is
    the only evidence available when a bug report describes a screen the
    developer's machine does not produce (`logging-rule.md` §3).
    """
    key = resolve_backtest_view_key(config)
    logger.info("Backtest view: %s", key.value)
    return _BUILDERS[key]()
