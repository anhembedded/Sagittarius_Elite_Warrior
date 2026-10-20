"""`BOT-209` — the kit's notice bar names its severity for a screen reader without naming a screen."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import (
    NoticeBar,
    NoticeKind,
)


def _icon_name(bar: NoticeBar) -> str:
    return bar.findChildren(QLabel)[0].accessibleName()


def test_each_severity_has_the_kits_own_words_and_a_consumer_may_say_what_it_means(
    qtbot,
) -> None:
    bar = NoticeBar(NoticeKind.CRITICAL, "bar")
    qtbot.addWidget(bar)

    assert _icon_name(bar) == "Error"
    bar.show_notice(NoticeKind.WARNING, "careful")
    assert (_icon_name(bar), bar.text, bar.kind) == (
        "Warning",
        "careful",
        NoticeKind.WARNING,
    )
    bar.show_notice(NoticeKind.CRITICAL, "no", "Blocks Start")
    assert _icon_name(bar) == "Blocks Start"
