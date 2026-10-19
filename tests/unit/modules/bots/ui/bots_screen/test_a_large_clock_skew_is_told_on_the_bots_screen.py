"""`BOT-182` — the Bots screen tells the owner when this machine's clock is far from the exchange's.

The Connect step measures the skew with every account read. Above one second, in
either direction, one bar says so; at or under it, nothing; an account that cannot
be read shows no skew bar. The notice refuses nothing.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.clock_skew_notice import (
    ClockSkewNotice,
    clock_skew_cause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.clock_skew_check import (
    FAIL_AT_MS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.clock_skew_limit import (
    CLOCK_SKEW_LIMIT_MS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

from .bots_screen_fixtures import stored
from .connect_screen_helpers import failure, fresh_snapshot, select

_SPOT = AccountSource.SPOT_TESTNET
_CAUSE = clock_skew_cause(_SPOT)


def _skew_bars(notifier: RecordingNotifier) -> list[str]:
    return [n.headline for n in notifier.failures if n.cause == _CAUSE]


def test_the_notice_and_the_headless_preflight_share_one_limit() -> None:
    assert FAIL_AT_MS == CLOCK_SKEW_LIMIT_MS == 1000


@pytest.mark.parametrize(
    ("skew_ms", "words"),
    [(1001, "1 s ahead of"), (-1001, "1 s behind"), (127_211, "127 s ahead of")],
)
def test_a_skew_above_one_second_is_one_bar_in_either_direction(
    skew_ms: int, words: str
) -> None:
    notifier = RecordingNotifier()

    ClockSkewNotice(notifier).observe(_SPOT, skew_ms)

    (notice,) = notifier.failures
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.scope == "bots"
    assert notice.cause == _CAUSE
    assert notice.retry is None
    assert words in notice.headline
    assert "Spot Testnet" in notice.headline


@pytest.mark.parametrize("skew_ms", [None, 0, 1000, -1000])
def test_at_or_under_one_second_or_unread_nothing_is_told(skew_ms: int | None) -> None:
    notifier = RecordingNotifier()

    ClockSkewNotice(notifier).observe(_SPOT, skew_ms)

    assert notifier.failures == [] and notifier.cleared == []


def test_it_is_told_once_per_episode_and_cleared_when_the_skew_is_back() -> None:
    notifier = RecordingNotifier()
    notice = ClockSkewNotice(notifier)

    notice.observe(_SPOT, 5000)
    notice.observe(_SPOT, 5200)
    assert len(notifier.failures) == 1

    notice.observe(_SPOT, 300)
    assert notifier.cleared == [_CAUSE]
    notice.observe(_SPOT, 300)
    assert notifier.cleared == [_CAUSE]

    notice.observe(_SPOT, -4000)
    assert len(notifier.failures) == 2


def test_each_venue_has_its_own_bar_and_a_moved_screen_drops_the_others() -> None:
    notifier = RecordingNotifier()
    notice = ClockSkewNotice(notifier)
    notice.observe(_SPOT, 5000)
    notice.observe(AccountSource.SPOT_MAINNET, 5000)
    assert {n.cause for n in notifier.failures} == {
        _CAUSE,
        clock_skew_cause(AccountSource.SPOT_MAINNET),
    }

    notice.keep_only(AccountSource.SPOT_MAINNET)

    assert notifier.cleared == [_CAUSE]


def test_the_connect_step_shows_the_bar_and_still_accepts_a_start(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), server_time_skew_ms=127_211))
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert len(_skew_bars(screen.notifier)) == 1
    rule = screen.view.model.availability[BotAction.START]
    assert "clock" not in rule.reason


def test_the_bar_goes_when_the_next_read_is_back_under_the_limit(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), server_time_skew_ms=-5000))
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert len(_skew_bars(screen.notifier)) == 1

    screen.account.answer_with(replace(fresh_snapshot(), server_time_skew_ms=40))
    screen.presenter._account._timer.timeout.emit()
    screen.settle()

    assert _CAUSE in screen.notifier.cleared


def test_an_account_that_cannot_be_read_shows_no_skew_bar_and_drops_a_shown_one(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), server_time_skew_ms=9000))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    screen.account.answer_with(failure(ConnectionFailureKind.NETWORK))
    screen.presenter._account._timer.timeout.emit()
    screen.settle()

    assert _CAUSE in screen.notifier.cleared
    assert len(_skew_bars(screen.notifier)) == 1
