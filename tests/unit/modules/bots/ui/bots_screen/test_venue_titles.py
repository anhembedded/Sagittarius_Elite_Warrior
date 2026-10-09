"""`EPIC-034A` — every place the Bots mode shows a venue shows its title."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotsTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.stop_bot_dialog import (
    stop_question,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .bots_screen_fixtures import NOW, stored


def _bot() -> BotSnapshot:
    return BotSnapshot.of(stored("a00001", BotLifecycleState.DRAFT).bot, None)


def test_the_table_the_read_out_and_the_stop_question_say_the_title() -> None:
    bot = _bot()
    assert bot.venue is TradingVenue.SPOT_TESTNET
    model = BotsTableModel()
    model.set_rows([bot])

    shown = model.data(model.index(0, model.column("venue")))

    assert shown == "Spot Testnet"
    assert bot_facts(bot, NOW).venue == "Spot Testnet"
    assert "Spot Testnet" in stop_question(bot)
    assert "spot_testnet" not in stop_question(bot)


def test_each_trading_venue_has_a_title_that_is_not_its_identifier() -> None:
    for venue in TradingVenue:
        assert venue.display_name and venue.display_name != venue.value
