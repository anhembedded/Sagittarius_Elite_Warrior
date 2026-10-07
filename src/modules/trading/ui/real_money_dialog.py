"""`EPIC-034` D3, D11 — the question that names real money, as a dialog.

@details `ui-presentation-rule.md` §10: the acting button says what it does, the
keeping one is the default and Esc keeps. Parented to whatever window is active, so
the question appears over the screen the person is acting on.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.modules.trading.application.real_money_consent import (
    RealMoneyQuestion,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.verb_confirmation import (
    VerbQuestion,
    ask_with_verbs,
)


def ask_real_money(question: RealMoneyQuestion) -> bool:
    venue = question.venue.display_name
    return ask_with_verbs(
        QApplication.activeWindow(),
        VerbQuestion(
            title="Real money",
            question=f"{venue} is a real account. Do you want to {question.action}?",
            act="Use real money",
            keep="Cancel",
            details=(
                f"Orders sent to {venue} spend real money and are filled by the "
                "real exchange. You are asked once for this venue until the "
                "application closes."
            ),
        ),
    )
