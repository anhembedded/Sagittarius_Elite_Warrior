"""`BOT-205` — the selected bot's fills read their Time column in the display time zone,
and are written again when the owner changes it."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFill,
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_activity_panels import (
    BotFillsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text


def _panel() -> tuple[BotFillsPanel, DisplayTimezonePreference]:
    model = BotsViewModel()
    panel = BotFillsPanel(model)
    preference = DisplayTimezonePreference()
    panel.use_display_timezone(preference)
    model.set_fills(
        BotFills(
            fills=(
                BotFill(
                    time=datetime(2026, 10, 4, 12, tzinfo=UTC),
                    side="SELL",
                    price=Decimal(64300),
                    quantity=Decimal("0.001"),
                    client_order_id="gbot-a00001-4",
                ),
            )
        )
    )
    return panel, preference


def _time_cell(panel: BotFillsPanel) -> str:
    return displayed_text(panel._table.view, 0, panel.fills.column("time"))


def test_the_time_column_is_utc_until_the_owner_chooses_a_zone(qapp) -> None:
    panel, _ = _panel()

    assert _time_cell(panel) == "2026-10-04 12:00:00"


def test_the_time_column_is_written_again_in_the_chosen_zone(qapp) -> None:
    panel, preference = _panel()

    preference.set_zone("Asia/Ho_Chi_Minh")

    assert _time_cell(panel) == "2026-10-04 19:00:00"


def test_the_screen_follows_the_display_zone_the_container_holds(
    open_bots_screen,
) -> None:
    """The wiring, against the screen's own composition: the zone the application remembers
    reaches the Fills table, and a choice made anywhere writes it again."""
    preference = DisplayTimezonePreference()
    preference.set_zone("Asia/Ho_Chi_Minh")
    screen = open_bots_screen(display_timezone=preference)
    screen.view.model.set_fills(
        BotFills(
            fills=(
                BotFill(
                    time=datetime(2026, 10, 4, 12, tzinfo=UTC),
                    side="SELL",
                    price=Decimal(64300),
                    quantity=Decimal("0.001"),
                    client_order_id="gbot-a00001-4",
                ),
            )
        )
    )
    table = screen.view.fills._table

    assert displayed_text(table.view, 0, screen.view.fills.fills.column("time")) == (
        "2026-10-04 19:00:00"
    )
    preference.set_zone("UTC")
    assert displayed_text(table.view, 0, screen.view.fills.fills.column("time")) == (
        "2026-10-04 12:00:00"
    )
