"""`EPIC-026L` — the day's result of the host's bots: the arithmetic and the day boundary (decision N3)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    BotObservation,
    LossCapLedger,
    day_start_of,
)

DAY = date(2026, 10, 20)
MIDNIGHT = day_start_of(DAY)
YESTERDAY_RUN = MIDNIGHT - timedelta(hours=9)
TODAY_RUN = MIDNIGHT + timedelta(hours=2)


def _seen(
    bot_id: str,
    pnl: str | None,
    run: datetime | None = YESTERDAY_RUN,
    *,
    at_rest: bool = False,
) -> BotObservation:
    return BotObservation(bot_id, run, None if pnl is None else Decimal(pnl), at_rest)


def test_a_run_from_before_midnight_counts_only_what_it_made_after_the_first_sample() -> (
    None
):
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", "-40")])
    assert ledger.day_pnl == 0  # the -40 was made before the ledger saw the bot
    assert ledger.observe([_seen("a", "-65.5")]).day_pnl == Decimal("-25.5")


def test_a_run_that_began_today_counts_its_whole_account() -> None:
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", "-12", TODAY_RUN)])
    assert ledger.day_pnl == Decimal(-12)


def test_the_day_is_the_sum_over_bots_and_a_gain_offsets_a_loss() -> None:
    ledger = LossCapLedger.empty(DAY).observe(
        [_seen("a", "-30", TODAY_RUN), _seen("b", "10", TODAY_RUN)]
    )
    assert ledger.day_pnl == Decimal(-20)


def test_a_new_run_banks_the_old_runs_day_and_starts_from_nothing() -> None:
    first = LossCapLedger.empty(DAY).observe([_seen("a", "-30", TODAY_RUN)])
    second_run = TODAY_RUN + timedelta(hours=3)
    after = first.observe([_seen("a", "-5", second_run)])
    assert after.day_pnl == Decimal(-35)
    assert after.observe([_seen("a", "-9", second_run)]).day_pnl == Decimal(-39)


def test_a_bot_with_no_readable_account_keeps_its_last_figure() -> None:
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", "-30", TODAY_RUN)])
    assert ledger.observe([_seen("a", None, TODAY_RUN)]).day_pnl == Decimal(-30)


def test_a_bot_that_is_gone_keeps_what_it_lost_today() -> None:
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", "-30", TODAY_RUN)])
    assert ledger.observe([]).day_pnl == Decimal(-30)


def test_a_bot_first_seen_with_no_readable_account_is_not_counted_as_zero_or_invented() -> (
    None
):
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", None)])
    assert dict(ledger.figures) == {}


def test_rebasing_accepts_the_loss_and_counts_from_the_latest_sample() -> None:
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", "-300", TODAY_RUN)])
    rebased = ledger.rebased()
    assert rebased.day_pnl == 0
    assert rebased.observe([_seen("a", "-310", TODAY_RUN)]).day_pnl == Decimal(-10)


def test_a_new_day_starts_a_new_ledger_whose_first_sample_is_its_baseline() -> None:
    today = LossCapLedger.empty(DAY).observe([_seen("a", "-300", TODAY_RUN)])
    tomorrow = LossCapLedger.empty(DAY + timedelta(days=1)).observe(
        [_seen("a", "-320", TODAY_RUN)]
    )
    assert today.day_pnl == Decimal(-300)
    assert tomorrow.day_pnl == 0
    assert tomorrow.observe([_seen("a", "-321", TODAY_RUN)]).day_pnl == Decimal(-1)


def test_a_run_that_began_a_second_before_midnight_is_not_today_s() -> None:
    just_before = MIDNIGHT - timedelta(seconds=1)
    ledger = LossCapLedger.empty(DAY).observe([_seen("a", "-7", just_before)])
    assert ledger.day_pnl == 0
    exactly = LossCapLedger.empty(DAY).observe([_seen("a", "-7", MIDNIGHT)])
    assert exactly.day_pnl == Decimal(-7)


def test_the_day_starts_at_midnight_utc() -> None:
    assert day_start_of(DAY) == datetime(2026, 10, 20, 0, 0, tzinfo=UTC)


def test_only_a_bot_that_may_hold_risk_and_has_no_result_is_unjudged() -> None:
    assert _seen("a", None).is_unjudged
    assert not _seen("a", None, at_rest=True).is_unjudged
    assert not _seen("a", "0").is_unjudged
