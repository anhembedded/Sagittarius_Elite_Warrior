"""`EPIC-034F` — the Design step on the real presenter: every constraint is
judged with the account's numbers, shown on its field with a useful number,
and a violation that blocks is the reason Start gives.

The account's balance is the Connect step's read (`EPIC-034D`); the plan is
the Grid editor's fields; the levels are drawn on the chart the screen shows.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import OverlayRole
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

from .bots_screen_fixtures import GOOD_CONFIG, stored
from .connect_screen_helpers import (
    chart_shown,
    fresh_snapshot,
    poor_account,
    select,
    start_rule,
)


def _panel(screen) -> GridPanel:
    panel = screen.view._kind_panel
    assert isinstance(panel, GridPanel)
    return panel


def _edit_capital(screen, text: str) -> None:
    panel = _panel(screen)
    panel.capital.setText(text)
    panel.capital.textEdited.emit(text)
    screen.presenter._refresh_detail()


def test_a_capital_above_the_balance_is_said_on_the_capital_field_with_the_number(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    poor_account(screen, Decimal(800))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    message = _panel(screen).field_error_text("capital_quote")

    assert message.startswith("Blocks Start: ")
    assert "need 995.48 USDT" in message
    assert "Spot Testnet has 800.00 USDT free" in message
    assert "at most 803.63" in message
    # Only the field the constraint is about carries it; the range's own
    # advice (the ATR) is another constraint's and does not block.
    assert not _panel(screen).field_error_text("lower").startswith("Blocks")
    assert _panel(screen).field_error_text("grid_count") == ""


def test_the_balance_blocks_start_and_names_itself_as_the_reason(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    poor_account(screen, Decimal(800))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    enabled, reason = start_rule(screen)

    assert not enabled
    assert "Spot Testnet has 800.00 USDT free" in reason


def test_lowering_the_capital_to_the_balance_clears_the_field_and_opens_start(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    poor_account(screen, Decimal(800))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    _edit_capital(screen, "800")

    assert _panel(screen).field_error_text("capital_quote") == ""
    assert "available" not in start_rule(screen)[1]


def test_a_key_that_cannot_trade_is_a_constraint_on_no_field(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), can_trade=False))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert not start_rule(screen)[0]
    assert "cannot trade" in start_rule(screen)[1]
    panel = _panel(screen)
    assert not any(
        panel.field_error_text(key)
        for key in ("grid_count", "spacing", "capital_quote")
    )


def test_the_plans_levels_are_drawn_on_the_chart_the_screen_shows(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert chart_shown(screen)
    overlay = screen.presenter._charts._chart._overlay
    roles = {line.role for line in overlay.lines}
    assert {OverlayRole.BUY_LEVEL, OverlayRole.SELL_LEVEL} <= roles
    prices = {
        line.price for line in overlay.lines if line.role is OverlayRole.BUY_LEVEL
    }
    assert min(prices) >= Decimal(GOOD_CONFIG["lower"])


def test_editing_the_range_redraws_the_levels(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    before = screen.presenter._charts._chart._overlay

    panel = _panel(screen)
    panel.lower_price.setText("62000")
    panel.lower_price.textEdited.emit("62000")
    screen.presenter._refresh_detail()
    after = screen.presenter._charts._chart._overlay

    assert after != before
    assert Decimal(62000) in {line.price for line in after.lines}
