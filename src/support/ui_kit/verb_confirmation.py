"""A risky action's question, answered with its own verbs (`EPIC-033I`).

`ui-presentation-rule.md` §10 and MS `mess-confirm`: confirm only risky or
irreversible actions, with specific verbs, never OK/Cancel or Yes/No, the
safe choice the default; Esc and the title bar's close keep the safe
choice. The Engine's `MessageBoxConfirmer` does this for a command declared
with a confirmation; this is the same dialog for a question a presenter asks
itself (placing an order, cancelling one, turning trading on), whose wording
depends on what is selected or typed.

Plausible extensions, each local: a question with a "don't ask" check box
(refused by the rule, so none); a third button (one parameter).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QMessageBox, QWidget


@dataclass(frozen=True)
class VerbQuestion:
    """What a risky action asks: a title naming the command (title case), the
    question, the details, the verb that acts and the one that keeps."""

    title: str
    question: str
    act: str
    keep: str
    details: str = ""


def ask_with_verbs(parent: QWidget | None, question: VerbQuestion) -> bool:
    """`True` when the person chose the acting verb; the keeping one is the
    default, and Esc keeps."""
    box = QMessageBox(
        QMessageBox.Icon.Question,
        question.title,
        question.question,
        QMessageBox.StandardButton.NoButton,
        parent,
    )
    if question.details:
        box.setInformativeText(question.details)
    act = box.addButton(question.act, QMessageBox.ButtonRole.AcceptRole)
    keep = box.addButton(question.keep, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(keep)
    box.setEscapeButton(keep)
    box.exec()
    return box.clickedButton() is act
