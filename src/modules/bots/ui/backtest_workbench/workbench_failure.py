"""`EPIC-040D` — what the person is told when a backtest or a sync raised (`BOT-169`): a headline in
words, the exception only as the notice's detail behind Details…."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench import (
    workbench_words as words,
)


def failure_notice(label: str, detail: str) -> FailureNotice:
    """The command failure for the action `label` ("backtest" or "sync")."""
    headline = words.FAILED_HEADLINES.get(label, words.FAILED_HEADLINES["backtest"])
    return FailureNotice(
        FailureKind.COMMAND, f"bots.backtest.{label}", headline, detail=detail
    )
