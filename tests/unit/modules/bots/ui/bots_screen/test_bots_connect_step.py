"""`EPIC-034D` — the Connect step on the Bots screen's real wiring.

A selected bot's venue account is read by itself; until it was read the chart
and the Plan are locked and say why, Start's reason names the connection, and
the identity strip shows the venue's title and the result. The account is the
verified fake reader, which answers what each test says and counts its reads.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_connect_fsm_matrix import (
    ConnectState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    RETRY_CONNECTION,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

from .bots_screen_fixtures import NOW, stored
from .connect_screen_helpers import (
    chart_shown,
    failure,
    fresh_snapshot,
    locked_note,
    select,
    start_rule,
)

_SPOT = AccountSource.SPOT_TESTNET


def test_until_the_account_is_read_the_chart_and_the_plan_wait(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    select(screen, "a00001")

    assert not chart_shown(screen)
    assert locked_note(screen) == "Spot Testnet: Reading the account…"
    assert not screen.view.plan.isEnabled()
    assert start_rule(screen) == (False, "Spot Testnet: Reading the account…")


def test_once_read_the_chart_and_the_plan_open_and_the_strip_says_who_and_where(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT, name="alpha")])
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert chart_shown(screen)
    assert screen.view.plan.isEnabled()
    assert screen.presenter._account.view.state is ConnectState.CONNECTED
    strip = screen.view.identity
    assert strip.isVisibleTo(screen.view)
    text = strip.who.text() + " | " + strip.connection.text()
    assert "alpha" in text
    assert "Spot Testnet" in text
    assert "spot_testnet" not in text
    assert "Connected" in text
    assert "50,000.00" in text
    assert "key can trade" in text
    assert screen.account.symbols_read == ["BTCUSDT"]


def test_an_exchange_under_maintenance_locks_both_and_says_so_with_a_retry(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(failure(ConnectionFailureKind.MAINTENANCE))
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert not chart_shown(screen)
    assert "under maintenance" in locked_note(screen)
    assert not screen.view.plan.isEnabled()
    enabled, reason = start_rule(screen)
    assert not enabled
    assert "under maintenance" in reason
    assert screen.actions.action(RETRY_CONNECTION).isEnabled()
    assert "Not connected" in screen.view.identity.connection.text()


def test_retrying_reads_again_and_opens_what_was_locked(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(failure(ConnectionFailureKind.KEY_REJECTED))
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert not chart_shown(screen)

    screen.account.answer_with(fresh_snapshot())
    screen.actions.action(RETRY_CONNECTION).trigger()
    screen.settle()

    assert chart_shown(screen)
    assert screen.view.plan.isEnabled()
    assert not screen.actions.action(RETRY_CONNECTION).isEnabled()
    assert len(screen.account.symbols_read) == 2


def test_a_key_that_cannot_trade_opens_the_chart_but_not_start(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), can_trade=False))
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert chart_shown(screen)
    enabled, reason = start_rule(screen)
    assert not enabled
    assert "cannot trade" in reason
    assert "Spot Testnet" in reason
    assert "key cannot trade" in screen.view.identity.connection.text()


def test_a_key_whose_permission_is_unknown_does_not_block_start(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), can_trade=None))
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert start_rule(screen)[0]
    assert "permission unknown" in screen.view.identity.connection.text()


def test_bots_on_the_same_venue_and_symbol_share_one_read(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("b00002", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    select(screen, "b00002")

    assert chart_shown(screen)  # already open: no wait for the pool
    screen.settle()
    assert screen.account.symbols_read == ["BTCUSDT"]


def test_a_read_that_is_no_longer_fresh_is_made_again(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("b00002", S.DRAFT)])
    screen.account.answer_with(
        replace(a_venue_account_snapshot(), read_at=NOW - timedelta(minutes=5))
    )
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    select(screen, "b00002")
    screen.settle()

    assert screen.account.symbols_read == ["BTCUSDT", "BTCUSDT"]


def test_the_answer_for_the_bot_left_behind_is_dropped(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("b00002", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    select(screen, "b00002")
    screen.account.answer_with(fresh_snapshot())

    screen.settle()

    assert screen.presenter._account.view.state is ConnectState.CONNECTED
    assert chart_shown(screen)


def test_the_timer_re_reads_and_a_failed_re_read_locks_the_chart(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert chart_shown(screen)

    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    screen.presenter._account._timer.timeout.emit()
    # While the re-read runs the connected chart stays.
    assert chart_shown(screen)
    screen.settle()

    assert not chart_shown(screen)
    assert "could not be reached" in locked_note(screen)
    assert len(screen.account.symbols_read) == 2


def test_selecting_nothing_ends_the_step_and_the_timer(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    select(screen, "")

    assert screen.presenter._account.view.state is ConnectState.NOT_CONNECTED
    assert not screen.presenter._account._timer.isActive()
    assert not screen.view.identity.isVisibleTo(screen.view)


def test_the_balance_is_the_snapshots_not_the_wallets(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), available=Decimal("1234.5")))
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert "1,234.5" in screen.view.identity.connection.text()


def test_the_status_bar_names_the_selected_bots_venue_by_its_title(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    (label,) = screen.view.status_widgets()
    assert not label.isVisibleTo(screen.view)

    select(screen, "a00001")
    screen.settle()

    assert label.isVisibleTo(screen.view)
    assert label.text() == "Bot venue: Spot Testnet, connected"

    screen.account.answer_with(failure(ConnectionFailureKind.MAINTENANCE))
    screen.presenter._account._timer.timeout.emit()
    screen.settle()

    assert label.text() == "Bot venue: Spot Testnet, not connected"


def test_a_failed_re_read_is_not_papered_over_by_the_read_before_it(
    open_bots_screen,
) -> None:
    """PR #417 review: bot A connects, a re-read then fails, and selecting bot B
    on the same symbol must read again, not share the earlier success."""
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("b00002", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    screen.presenter._account._timer.timeout.emit()
    screen.settle()
    assert not chart_shown(screen)

    select(screen, "b00002")

    assert screen.presenter._account.view.state is ConnectState.CONNECTING
    assert not chart_shown(screen)
    screen.settle()
    assert screen.presenter._account.view.state is ConnectState.FAILED
    assert len(screen.account.symbols_read) == 3
