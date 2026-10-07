"""`BOT-171` — a draft bot changes its Spot venue from the Plan's Venue field.

@details On the Bots screen's real wiring; the venues' accounts, order histories
and market data are their verified fakes, so nothing reaches an exchange and no
order is placed. A draft that never ran may move between the Spot venues; after the
move the Connect step reads the new venue's account, the chart reads the new venue's
market and readiness is judged on both. A bot that ran or runs keeps its venue.
Switching to Spot Mainnet asks nothing here: the real-money question is Start's
(`EPIC-034` D11).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    KEY_SAVED,
    NO_KEY,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .bots_market_fixtures import MAINNET
from .bots_screen_fixtures import SYMBOL, VENUE, BotsScreen, stored
from .connect_screen_helpers import chart_shown, failure, select


def _pick(screen: BotsScreen, venue: TradingVenue) -> None:
    """What the user does in the Plan's Venue field: choose, and the screen acts."""
    combo = screen.view.plan.venue
    index = combo.findData(venue.value)
    combo.setCurrentIndex(index)
    combo.activated.emit(index)
    screen.settle()


def _venue_of(screen: BotsScreen, bot_id: str) -> TradingVenue:
    return screen.store.load(BotId(bot_id)).bot.definition.venue


def test_the_field_lists_every_spot_venue_with_its_connection_state(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    combo = screen.view.plan.venue
    assert [combo.itemText(i) for i in range(combo.count())] == [
        f"Spot Testnet — {KEY_SAVED}",
        f"Spot Mainnet — {KEY_SAVED}",
    ]
    assert combo.currentData() == VENUE.value
    assert combo.isEnabled()


def test_a_draft_moved_to_spot_mainnet_reads_mainnets_account_and_market(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT, name="alpha")])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert screen.account.symbols_read == [SYMBOL]
    assert screen.market_sources.asked == [VENUE.market_data_venue]

    _pick(screen, MAINNET)

    assert _venue_of(screen, "a00001") is MAINNET
    assert screen.mainnet_account.symbols_read == [SYMBOL]
    assert screen.account.symbols_read == [SYMBOL]
    assert screen.market_sources.asked == [
        VENUE.market_data_venue,
        MAINNET.market_data_venue,
    ]
    assert chart_shown(screen)
    account = screen.presenter._account
    assert account.view.venue == "Spot Mainnet"
    assert account.view.state is ReadinessState.DESIGNING
    assert "Spot Mainnet" in screen.view.identity.connection.text()
    assert screen.view.plan.venue.currentData() == MAINNET.value


def test_moving_to_spot_mainnet_asks_no_confirmation(open_bots_screen) -> None:
    """The real-money question runs at Start (`EPIC-034` D11), not here."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    _pick(screen, MAINNET)

    assert screen.answers.asked == []
    assert screen.notifier.failures_of(FailureKind.COMMAND) == []


def test_the_new_venues_account_is_judged_not_the_old_ones(open_bots_screen) -> None:
    """Readiness is recomputed on the new venue: its account refuses, the bot is
    not connected, and the Connect item names the new venue."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.mainnet_account.answer_with(
        failure(ConnectionFailureKind.KEY_REJECTED).__class__(
            screen.mainnet_account.source, ConnectionFailureKind.KEY_REJECTED, "x"
        )
    )
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert screen.presenter._account.view.state is ReadinessState.DESIGNING

    _pick(screen, MAINNET)

    assert screen.presenter._account.view.state is ReadinessState.FAILED
    assert not chart_shown(screen)
    items = screen.view.plan.readiness_items.text()
    assert "Spot Mainnet: Not connected: key refused" in items
    causes = [n.cause for n in screen.notifier.failures_of(FailureKind.BACKGROUND)]
    assert [c for c in causes if c.startswith("bots.")] == ["bots.connect.spot_mainnet"]


def test_parameters_not_yet_saved_stay_on_screen_across_the_move(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    panel = screen.view._kind_panel
    panel.capital.setText("1500")
    panel.capital.textEdited.emit("1500")

    _pick(screen, MAINNET)

    shown = screen.view._kind_panel
    assert shown is not None and shown.capital.text() == "1500"
    assert dict(screen.presenter._selected.edited or {})["capital_quote"] == "1500"
    stored_config = screen.store.load(BotId("a00001")).bot.definition.config
    assert stored_config["capital_quote"] != "1500"


def test_a_running_bot_refuses_the_move_and_keeps_its_venue(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    combo = screen.view.plan.venue
    assert not combo.isEnabled()
    assert "fixed once it has run" in combo.toolTip()

    # Asked anyway, as a stray signal would: the command refuses it in words.
    screen.view.model.venue_change_requested.emit(MAINNET.value)
    screen.settle()

    assert _venue_of(screen, "a00001") is VENUE
    assert screen.mainnet_account.symbols_read == []
    refusal = screen.notifier.failures_of(FailureKind.COMMAND)[-1]
    assert "fixed once it has run" in refusal.headline
    assert screen.view.plan.venue.currentData() == VENUE.value


def test_a_stopped_bot_has_run_and_keeps_its_venue(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.STOPPED)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert not screen.view.plan.venue.isEnabled()


def test_new_bot_offers_every_spot_venue_with_its_connection_state(
    open_bots_screen,
) -> None:
    from .bots_screen_fixtures import Answers

    answers = Answers()
    screen = open_bots_screen(answers=answers)
    screen.settle()

    screen.view.model.new_bot_requested.emit()
    screen.settle()

    assert answers.offered == [
        f"Spot Testnet — {KEY_SAVED}",
        f"Spot Mainnet — {KEY_SAVED}",
    ]
    assert NO_KEY not in " ".join(answers.offered)
