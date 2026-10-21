"""`EPIC-043E` — the editor's Liquidation row paints each side in the tone the guard's own severity
gives it, and keeps the words that say the same."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import BotsView
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview_frames import (
    build_frame,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    NOT_ESTIMATED,
    LiquidationLine,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.liquidation_readout import (
    LiquidationReadout,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.verdict_tone import verdict_tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

_REFUSED = LiquidationLine(
    "long", "Blocks Start: Long: liquidation near 54,000.00", VerdictSeverity.REFUSED
)
_WARNED = LiquidationLine(
    "short", "Advice: Short: liquidation near 66,000.00", VerdictSeverity.WARNING
)
_FINE = LiquidationLine(
    "short", "Short: liquidation near 70,000.00 (estimate)", VerdictSeverity.OK
)


def _colour(label: QLabel) -> object:
    return label.palette().color(label.foregroundRole())


def _plain(label: QLabel) -> object:
    return QPalette().color(label.foregroundRole())


def _tone(tone: Tone) -> object:
    return tone_colour(tone, QGuiApplication.palette())


def test_every_severity_has_a_tone_and_only_a_pass_has_none() -> None:
    assert {s: verdict_tone(s) for s in VerdictSeverity} == {
        VerdictSeverity.REFUSED: Tone.NEGATIVE,
        VerdictSeverity.WARNING: Tone.CAUTION,
        VerdictSeverity.OK: Tone.NEUTRAL,
    }


def test_before_the_guard_has_judged_a_plan_the_row_is_one_plain_line(qtbot) -> None:
    row = LiquidationReadout()
    qtbot.addWidget(row)

    assert row.text() == NOT_ESTIMATED
    assert _colour(row.label_of(0)) == _plain(row.label_of(0))


def test_each_side_takes_its_own_severitys_tone(qtbot) -> None:
    """A Neutral plan can have one side refused and the other fine: one tone over both lines
    would paint the fine side as the refused one."""
    row = LiquidationReadout()
    qtbot.addWidget(row)

    row.show_lines((_REFUSED, _FINE))

    assert _colour(row.label_of(0)) == _tone(Tone.NEGATIVE)
    assert _colour(row.label_of(1)) == _plain(row.label_of(1))
    assert row.text().splitlines()[0].startswith("Blocks Start:")


def test_a_warning_reads_in_the_caution_tone_with_its_advice_word(qtbot) -> None:
    row = LiquidationReadout()
    qtbot.addWidget(row)

    row.show_lines((_WARNED,))

    assert _colour(row.label_of(0)) == _tone(Tone.CAUTION)
    assert row.text().startswith("Advice:")


def test_a_fresh_judgement_replaces_the_lines_and_their_tones(qtbot) -> None:
    row = LiquidationReadout()
    qtbot.addWidget(row)
    row.show_lines((_REFUSED, _WARNED))

    row.show_lines((_FINE,))

    assert row.text() == _FINE.text
    assert _colour(row.label_of(0)) == _plain(row.label_of(0))
    row.show_lines(())
    assert row.text() == NOT_ESTIMATED


# -- through the real planner's verdicts ---------------------------------------------------------


def _row(view: BotsView) -> LiquidationReadout:
    panel = view.findChild(GridPanel)
    assert panel is not None
    return panel.exposure.liquidation


def test_a_refused_plan_paints_its_liquidation_line_as_a_loss(qtbot) -> None:
    view = build_frame("futures_refused_plan")
    qtbot.addWidget(view)

    row = _row(view)

    assert row.text().startswith("Blocks Start:")
    assert _colour(row.label_of(0)) == _tone(Tone.NEGATIVE)


def test_a_warned_plan_paints_its_liquidation_line_in_caution(qtbot) -> None:
    view = build_frame("futures_liquidation_warning")
    qtbot.addWidget(view)

    row = _row(view)

    assert row.text().startswith("Advice:")
    assert _colour(row.label_of(0)) == _tone(Tone.CAUTION)
