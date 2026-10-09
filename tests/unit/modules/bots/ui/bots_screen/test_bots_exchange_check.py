"""`BOT-174` — the selected bot's exchange snapshot on the real presenter.

@details A bot at rest or halted has a Start or a Resume whose rules need the
exchange's facts. The screen asks for them off the UI thread when the bot is
selected, on demand, and when its state changes; until they arrive the Run step says
"Checking the exchange…" and Start is off, a read that failed is named, and an answer
that is no longer current is dropped (`async-ui-action-rule.md` §1). Every read the
tests hold is released by hand, so the order of answers is the test's.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotDefinition
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    REFRESH_EXCHANGE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)

from .bots_screen_fixtures import GOOD_CONFIG, VENUE, BotsScreen, stored
from .connect_screen_helpers import poor_account, select, start_rule


def _exchange_reads(screen: BotsScreen) -> list[int]:
    return [
        index
        for index, (_, args) in enumerate(screen.pool.pending)
        if args[:1] == (ReadKind.EXCHANGE,)
    ]


def _run_all_but_the_exchange(screen: BotsScreen) -> None:
    while True:
        others = [
            index
            for index in range(len(screen.pool.pending))
            if index not in _exchange_reads(screen)
        ]
        if not others:
            return
        screen.pool.run(others[0])


def _snapshot(screen: BotsScreen):
    return screen.presenter._selected.exchange


def _run_step_lines(screen: BotsScreen) -> str:
    return screen.view.plan.readiness_items.text()


def _the_selected_bot_is_asked_about(screen: BotsScreen) -> None:
    screen.settle()
    select(screen, "a00001")


# --- loading -----------------------------------------------------------------


def test_until_the_exchange_answers_the_run_step_says_so_and_start_is_off(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    _the_selected_bot_is_asked_about(screen)
    _run_all_but_the_exchange(screen)

    assert isinstance(_snapshot(screen), ExchangeChecking)
    assert "Run: Checking the exchange…" in _run_step_lines(screen)
    enabled, reason = start_rule(screen)
    assert not enabled
    assert reason == "1 thing left: Checking the exchange…"

    screen.settle()

    assert isinstance(_snapshot(screen), ExchangeLoaded)
    assert start_rule(screen)[0]
    assert _run_step_lines(screen) == ""


# --- unavailable --------------------------------------------------------------


def test_an_exchange_that_did_not_answer_is_named_and_a_refresh_asks_again(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    working = screen.exchange_account.check_connection()
    screen.exchange_account.answer_with(
        replace(working, reachable=False, failure=ConnectionFailureKind.NETWORK)
    )
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert isinstance(_snapshot(screen), ExchangeUnavailable)
    line = _run_step_lines(screen)
    assert (
        "The exchange's facts could not be read: Not connected: exchange unreachable"
        in line
    )
    assert "→ Bots → Refresh exchange check" in line
    assert not start_rule(screen)[0]

    screen.exchange_account.answer_with(working)
    screen.actions.action(REFRESH_EXCHANGE).trigger()
    assert isinstance(_snapshot(screen), ExchangeChecking)
    screen.settle()

    assert isinstance(_snapshot(screen), ExchangeLoaded)
    assert start_rule(screen)[0]


def test_a_read_that_itself_failed_is_unavailable_with_its_text_and_no_second_bar(
    open_bots_screen, monkeypatch
) -> None:
    """The reader never raises, so this is a fault of the app: it is the
    snapshot's own unavailable state, not a message bar beside it."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])

    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(screen.exchange_account, "check_connection", boom)
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    snapshot = _snapshot(screen)
    assert isinstance(snapshot, ExchangeUnavailable)
    assert "boom" in snapshot.reason
    assert not [n for n in screen.notifier.failures if "exchange" in n.cause]
    assert not start_rule(screen)[0]


# --- fencing and cancellation ---------------------------------------------------


def test_the_facts_of_the_bot_left_behind_are_never_judged_for_the_next_one(
    open_bots_screen,
) -> None:
    ether = StoredBot(
        replace(
            stored("a00002", S.DRAFT).bot,
            definition=BotDefinition("eth", "grid", VENUE, "ETHUSDT", GOOD_CONFIG),
        )
    )
    screen = open_bots_screen([stored("a00001", S.DRAFT), ether])
    screen.settle()
    select(screen, "a00001")
    select(screen, "a00002")
    first = next(
        i
        for i, (_, args) in enumerate(screen.pool.pending)
        if args[:1] == (ReadKind.EXCHANGE,) and args[2] == "a00001"
    )

    screen.pool.run(first)  # the first bot's answer arrives late

    assert isinstance(_snapshot(screen), ExchangeChecking)
    screen.settle()
    snapshot = _snapshot(screen)
    assert isinstance(snapshot, ExchangeLoaded)
    assert snapshot.facts.symbol == "ETHUSDT"


def test_a_request_replaced_by_a_newer_one_is_dropped_when_it_answers(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    _the_selected_bot_is_asked_about(screen)
    screen.settle()
    screen.view.model.refresh_exchange_requested.emit()
    screen.view.model.refresh_exchange_requested.emit()
    older, newer = _exchange_reads(screen)

    screen.pool.run(older)

    assert isinstance(_snapshot(screen), ExchangeChecking)
    screen.pool.run(newer - 1)
    assert isinstance(_snapshot(screen), ExchangeLoaded)


def test_selecting_a_bot_with_nothing_to_check_cancels_the_ask_in_flight(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("a00002", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    select(screen, "a00002")

    assert not [
        i for i in _exchange_reads(screen) if screen.pool.pending[i][1][2] == "a00002"
    ]
    screen.settle()

    assert isinstance(_snapshot(screen), ExchangeChecking)
    assert screen.presenter._selected.bot.bot_id == "a00002"


def test_an_answer_after_the_screen_closed_is_dropped(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    _run_all_but_the_exchange(screen)

    screen.presenter.dispose()
    screen.settle()

    assert isinstance(_snapshot(screen), ExchangeChecking)


# --- refreshed when the state changes -----------------------------------------


def test_a_bot_that_becomes_halted_is_asked_about_again(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert _exchange_reads(screen) == []

    screen.store.save(stored("a00001", S.HALTED))
    screen.presenter._queries.bots()
    screen.pool.run_all()

    assert isinstance(_snapshot(screen), ExchangeLoaded)
    assert screen.exchange_account.connection_checks >= 1


def test_a_bot_whose_state_did_not_move_is_not_asked_again_by_a_list_read(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    _the_selected_bot_is_asked_about(screen)
    screen.settle()
    checks = screen.exchange_account.connection_checks

    screen.presenter._queries.bots()
    screen.settle()

    assert screen.exchange_account.connection_checks == checks


# --- the Resume button on a halted bot ----------------------------------------


def _halted_with_inventory() -> StoredBot:
    halted = stored("a00001", S.HALTED)
    runtime = GridRuntime((), inventory=Decimal("0.05"), cost=Decimal(3000))
    return StoredBot(halted.bot, encode_runtime(runtime))


def test_resume_is_off_with_the_shortfall_while_the_free_base_cannot_cover_the_sells(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([_halted_with_inventory()])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    rule = screen.view.model.availability[BotAction.RESUME]

    assert not rule.enabled
    assert rule.reason.startswith("Resume is blocked: The resumed ladder sells ")
    assert "BTC free" in rule.reason

    status = screen.exchange_account.check_connection()
    screen.exchange_account.answer_with(
        replace(
            status,
            holdings=(
                SpotHolding("BTC", Decimal(1), Decimal(0), Decimal(0)),
                *status.holdings,
            ),
        )
    )
    screen.view.model.refresh_exchange_requested.emit()
    screen.settle()

    assert screen.view.model.availability[BotAction.RESUME].enabled


def test_resume_waits_for_the_exchange_like_start_does(open_bots_screen) -> None:
    screen = open_bots_screen([_halted_with_inventory()])
    screen.settle()
    select(screen, "a00001")
    _run_all_but_the_exchange(screen)

    rule = screen.view.model.availability[BotAction.RESUME]

    assert not rule.enabled
    assert rule.reason == "Resume is blocked: Checking the exchange…"


def test_a_poor_account_is_refused_on_the_screen_with_the_same_words_start_gives(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    poor_account(screen, Decimal(800))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert start_rule(screen)[1].startswith(
        "1 thing left: The opening buy and the BUY levels need "
    )


def test_a_command_that_finished_asks_the_exchange_again(open_bots_screen) -> None:
    """Accepted or refused, what it did may have moved the account (an order
    placed, a base kept), so the facts the next click is judged on are read anew."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    _the_selected_bot_is_asked_about(screen)
    screen.settle()
    checks = screen.exchange_account.connection_checks

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    assert screen.exchange_account.connection_checks == checks + 1


def test_resume_is_off_while_the_market_numbers_are_still_being_read(
    open_bots_screen,
) -> None:
    """Fail closed, as Start does: with the exchange loaded but no plan to draw,
    the resume is not called ready."""
    screen = open_bots_screen([_halted_with_inventory()])
    screen.settle()
    select(screen, "a00001")
    while True:
        ready = [
            index
            for index, (_, args) in enumerate(screen.pool.pending)
            if args[:1] != (ReadKind.PLANNER,)
        ]
        if not ready:
            break
        screen.pool.run(ready[0])

    rule = screen.view.model.availability[BotAction.RESUME]

    assert isinstance(_snapshot(screen), ExchangeLoaded)
    assert not rule.enabled
    assert (
        rule.reason
        == "Resume is blocked: The market numbers for this symbol are still being read."
    )

    screen.settle()

    assert (
        "market numbers" not in screen.view.model.availability[BotAction.RESUME].reason
    )
