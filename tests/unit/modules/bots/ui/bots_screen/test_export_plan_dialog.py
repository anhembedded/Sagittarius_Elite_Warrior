"""`BOT-176` - the Export plan… dialog: its defaults follow real money, and it returns the person's choice."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QPushButton
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    COPY_TEXT,
    NOTE,
    SAVE_TEXT,
    ExportPlanAction,
    ExportPlanChoice,
    ExportPlanDialog,
    ExportPlanScope,
    default_all_stopped,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview import (
    build_export_plan_preview,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _bot(bot_id: str, venue: TradingVenue) -> BotSnapshot:
    return BotSnapshot(
        bot_id,
        f"bot {bot_id}",
        "grid",
        venue,
        "BTCUSDT",
        BotLifecycleState.RUNNING,
        datetime(2026, 10, 14, tzinfo=UTC),
        None,
    )


_TESTNET = _bot("a00001", TradingVenue.SPOT_TESTNET)
_MAINNET = _bot("b00002", TradingVenue.SPOT_MAINNET)


def _press(dialog: ExportPlanDialog, text: str) -> None:
    buttons = dialog.findChild(QDialogButtonBox)
    (button,) = (b for b in buttons.findChildren(QPushButton) if b.text() == text)
    button.click()


@pytest.mark.parametrize(
    ("venue", "stopped"),
    [
        (TradingVenue.SPOT_TESTNET, False),
        (TradingVenue.FUTURES_TESTNET, False),
        (TradingVenue.SPOT_MAINNET, True),
        (TradingVenue.FUTURES_MAINNET, True),
    ],
)
def test_the_default_state_follows_whether_a_bot_is_on_a_mainnet_venue(
    venue: TradingVenue, stopped: bool
) -> None:
    assert default_all_stopped([_bot("c00003", venue)]) is stopped
    assert default_all_stopped([]) is False


def test_selected_is_unavailable_without_a_selection_and_all_is_chosen(qapp) -> None:
    dialog = ExportPlanDialog([_TESTNET, _MAINNET], None)

    assert not dialog.selected_only.isEnabled()
    assert dialog.every_bot.isChecked()
    # All bots includes a mainnet bot, so the safe state is the default.
    assert dialog.stopped.isChecked() and not dialog.keep.isChecked()


def test_with_a_selection_the_dialog_starts_on_it_and_keeps_a_testnet_bots_state(
    qapp,
) -> None:
    dialog = ExportPlanDialog([_TESTNET, _MAINNET], _TESTNET)

    assert dialog.selected_only.isEnabled() and dialog.selected_only.isChecked()
    assert dialog.keep.isChecked() and not dialog.stopped.isChecked()


def test_the_default_follows_the_scope_until_the_person_picks_a_state(qapp) -> None:
    dialog = ExportPlanDialog([_TESTNET, _MAINNET], _TESTNET)

    dialog.every_bot.setChecked(True)
    assert dialog.stopped.isChecked()
    dialog.selected_only.setChecked(True)
    assert dialog.keep.isChecked()

    dialog.keep.click()
    dialog.every_bot.setChecked(True)

    assert dialog.keep.isChecked(), "a chosen state is not overruled by the default"


def test_it_says_the_plan_holds_no_key_and_the_server_judges_it_again(qapp) -> None:
    assert "no API key" in NOTE
    assert "bot apply <file> --dry-run" in NOTE
    assert "`" not in NOTE, "a label shows text as written, so no Markdown"


@pytest.mark.parametrize(
    ("text", "action"),
    [(SAVE_TEXT, ExportPlanAction.SAVE), (COPY_TEXT, ExportPlanAction.COPY)],
)
def test_each_button_returns_the_choice_with_its_action(
    qapp, text: str, action: ExportPlanAction
) -> None:
    dialog = ExportPlanDialog([_TESTNET, _MAINNET], _TESTNET)
    dialog.stopped.click()

    _press(dialog, text)

    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.choice() == ExportPlanChoice(ExportPlanScope.SELECTED, True, action)


def test_close_accepts_nothing(qapp) -> None:
    dialog = ExportPlanDialog([_TESTNET], _TESTNET)

    _press(dialog, "Close")

    assert dialog.result() == dialog.DialogCode.Rejected


def test_the_preview_frame_builds_with_a_mainnet_bot_in_scope(qtbot) -> None:
    dialog = build_export_plan_preview()
    qtbot.addWidget(dialog)

    assert isinstance(dialog, ExportPlanDialog)
    assert not dialog.grab().isNull()
    dialog.every_bot.setChecked(True)
    assert dialog.stopped.isChecked()
