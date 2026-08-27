"""Reading a timeframe the user may have left in an unusable state.

@details `EPIC-012G`. Split out of `BackTestPresenter` because the fallback
here had been broken since `e071c8d` (2026-08-22) and nothing noticed: the
recovery branch named `TimeFrame.M1`, a member that does not exist, so the
`except ValueError` handler raised `AttributeError` instead of recovering.
No test covered it, and `ruff` cannot see it — an `Enum` member is a dynamic
attribute to a linter.

Pulling it into its own module is what makes it testable at all. The two
call sites in `_build_run_config` deliberately do NOT use this: building a
config for a real run is the validating path, where an unusable timeframe
must raise rather than quietly become something else.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

logger = logging.getLogger("App.BacktestTimeframe")

#: What an unreadable timeframe falls back to. `ONE_MINUTE` rather than any
#: other member because `BackTestViewModel` already starts there
#: (`DEFAULT_TIMEFRAMES[0]`), so the recovered value matches what the toolbar
#: is showing — the fastest timeframe, and the one most likely to have data.
FALLBACK_TIMEFRAME = TimeFrame.ONE_MINUTE


def timeframe_or_fallback(raw: str) -> TimeFrame:
    """The `TimeFrame` for `raw`, or `FALLBACK_TIMEFRAME` if it is unusable.

    @details Warns rather than recovering silently: a value that reaches here
    and does not parse means the ViewModel holds something no picker can
    produce — a hand-edited `user_config.json`, or restored state from a
    build whose timeframe list has since changed. That is a broken-state
    signal, and `logging-rule.md` §2 requires the fallback branch say so.
    """
    try:
        return TimeFrame(raw)
    except ValueError:
        logger.warning(
            "Timeframe %r is not a known TimeFrame; falling back to %s. "
            "The ViewModel is holding a value no picker can produce — check "
            "user_config.json and any restored ui_state.",
            raw,
            FALLBACK_TIMEFRAME.value,
        )
        return FALLBACK_TIMEFRAME
