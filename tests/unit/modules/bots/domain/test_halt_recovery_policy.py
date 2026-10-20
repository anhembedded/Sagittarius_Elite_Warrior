"""`EPIC-042B` — the halt-recovery policy is three layers of data, merged in a fixed order.

ADR 042 §2.3: fold common, kind, venue; a layer clears the lower ones, withdraws codes, then
changes rules; later wins. Each layer and the merged result is a value compared here, and the
real layers (`COMMON_LAYER`, the Grid's, Spot's and Futures') are checked for what the owner
decided: Spot keeps the common set, Futures recovers nothing.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GRID_RECOVERY_LAYER,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    COMMON_LAYER,
    DEFAULT_RULE,
    MAX_RECORDED_ATTEMPTS,
    PRICE_FEED_STALE,
    USER_STREAM_DOWN,
    HaltCode,
    HaltRecoveryRule,
    RecoveryLayer,
    RuleChange,
    effective_policy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

NOTHING = RecoveryLayer("nothing")
RATE_LIMITED = HaltCode("rate_limited")
SECOND = timedelta(seconds=1)


def _merged(kind: RecoveryLayer = NOTHING, venue: RecoveryLayer = NOTHING):
    return effective_policy(COMMON_LAYER, kind, venue)


def test_the_codes_are_the_names_the_grid_records_its_halts_with() -> None:
    assert GridReason.PRICE_FEED_STALE.value == PRICE_FEED_STALE
    assert GridReason.USER_STREAM_DOWN.value == USER_STREAM_DOWN


def test_the_default_rule_is_the_owners_figures() -> None:
    assert DEFAULT_RULE.dwell == timedelta(seconds=120)
    assert DEFAULT_RULE.max_attempts == 3
    assert DEFAULT_RULE.window == timedelta(hours=24)
    assert DEFAULT_RULE.stalled_after == timedelta(minutes=15)


def test_the_common_layer_alone_recovers_a_quiet_feed_and_a_down_stream() -> None:
    policy = _merged()
    assert [row.code for row in policy.rows] == [PRICE_FEED_STALE, USER_STREAM_DOWN]
    assert all(row.rule == DEFAULT_RULE for row in policy.rows)
    assert {row.decided_by for row in policy.rows} == {"common"}


def test_a_kind_adds_a_reason_the_common_layer_does_not_have() -> None:
    kind = RecoveryLayer("grid", changes={RATE_LIMITED: RuleChange()})
    row = {r.code: r for r in _merged(kind).rows}[RATE_LIMITED]
    assert row.rule == DEFAULT_RULE
    assert row.decided_by == "grid"


def test_a_change_sets_one_field_and_keeps_the_rest_from_the_lower_layers() -> None:
    kind = RecoveryLayer(
        "grid", changes={PRICE_FEED_STALE: RuleChange(dwell=SECOND * 30)}
    )
    row = {r.code: r for r in _merged(kind).rows}[PRICE_FEED_STALE]
    assert row.rule == HaltRecoveryRule(
        SECOND * 30,
        DEFAULT_RULE.max_attempts,
        DEFAULT_RULE.window,
        DEFAULT_RULE.stalled_after,
    )
    assert row.decided_by == "grid"


def test_a_later_layer_wins_over_an_earlier_one() -> None:
    kind = RecoveryLayer(
        "grid", changes={PRICE_FEED_STALE: RuleChange(dwell=SECOND * 30)}
    )
    venue = RecoveryLayer(
        "spot", changes={PRICE_FEED_STALE: RuleChange(dwell=SECOND * 45)}
    )
    row = {r.code: r for r in _merged(kind, venue).rows}[PRICE_FEED_STALE]
    assert row.rule.dwell == SECOND * 45
    assert row.decided_by == "spot"


def test_a_kind_can_withdraw_a_common_reason_and_the_venue_can_put_it_back() -> None:
    kind = RecoveryLayer("grid", withdrawn=frozenset({USER_STREAM_DOWN}))
    assert [r.code for r in _merged(kind).rows] == [PRICE_FEED_STALE]
    venue = RecoveryLayer("spot", changes={USER_STREAM_DOWN: RuleChange()})
    restored = {r.code: r for r in _merged(kind, venue).rows}[USER_STREAM_DOWN]
    assert restored.decided_by == "spot"


def test_a_layer_that_clears_the_lower_ones_leaves_only_what_it_adds() -> None:
    venue = RecoveryLayer(
        "venue", clears_lower_layers=True, changes={RATE_LIMITED: RuleChange()}
    )
    assert [r.code for r in _merged(venue=venue).rows] == [RATE_LIMITED]


def test_a_layer_cannot_both_withdraw_and_change_a_code() -> None:
    with pytest.raises(ValueError, match="both withdraws and changes"):
        RecoveryLayer(
            "bad",
            withdrawn=frozenset({RATE_LIMITED}),
            changes={RATE_LIMITED: RuleChange()},
        )


@pytest.mark.parametrize(
    "change",
    [
        RuleChange(dwell=timedelta(0)),
        RuleChange(max_attempts=0),
        RuleChange(max_attempts=MAX_RECORDED_ATTEMPTS + 1),
        RuleChange(window=timedelta(0)),
        RuleChange(stalled_after=timedelta(seconds=120)),
        RuleChange(dwell=timedelta(minutes=20)),
    ],
)
def test_a_layer_that_builds_an_invalid_rule_fails_when_the_policy_is_built(
    change: RuleChange,
) -> None:
    kind = RecoveryLayer("grid", changes={PRICE_FEED_STALE: change})
    with pytest.raises(ValueError):
        _merged(kind)


def test_spot_keeps_the_common_set_and_the_grids_pause() -> None:
    spot = venue_profile_of(TradingVenue.SPOT_MAINNET)
    assert spot is not None
    policy = effective_policy(COMMON_LAYER, GRID_RECOVERY_LAYER, spot.recovery_layer)
    assert [row.code for row in policy.rows] == [
        PRICE_FEED_STALE,
        RATE_LIMITED,
        USER_STREAM_DOWN,
    ]
    pause = {row.code: row for row in policy.rows}[RATE_LIMITED]
    assert pause.decided_by == GRID_KIND_ID
    assert pause.rule.dwell == timedelta(seconds=2)
    assert pause.rule.max_attempts == DEFAULT_RULE.max_attempts, (
        "the one budget per bot"
    )


@pytest.mark.parametrize(
    "venue", [TradingVenue.FUTURES_MAINNET, TradingVenue.FUTURES_TESTNET]
)
def test_futures_recovers_only_the_exchanges_pause_whatever_a_kind_adds(
    venue: TradingVenue,
) -> None:
    """ADR 042 D5: its halt closes the position and `EPIC-039L` governs it, so it clears every
    lower layer; the exchange's pause is the one reason it lists (`EPIC-042F`, `BUG-216`)."""
    futures = venue_profile_of(venue)
    assert futures is not None
    greedy = RecoveryLayer(
        GRID_KIND_ID,
        changes={HaltCode("order_rejected"): RuleChange(), RATE_LIMITED: RuleChange()},
    )
    policy = effective_policy(COMMON_LAYER, greedy, futures.recovery_layer)
    assert [row.code for row in policy.rows] == [RATE_LIMITED]
    [pause] = policy.rows
    assert pause.decided_by == "futures"
    assert pause.rule.dwell == timedelta(seconds=2)


def test_the_policy_answers_for_one_code_and_for_the_longest_window() -> None:
    policy = _merged()
    assert policy.rule_for(PRICE_FEED_STALE) == DEFAULT_RULE
    assert policy.rule_for(HaltCode("order_rejected")) is None
    assert policy.longest_window == DEFAULT_RULE.window


def test_a_rule_may_allow_as_many_attempts_as_the_record_keeps_and_no_more() -> None:
    """With more, the ledger's cap would drop old attempts and the budget would never run out."""
    kind = RecoveryLayer(
        "grid",
        changes={PRICE_FEED_STALE: RuleChange(max_attempts=MAX_RECORDED_ATTEMPTS)},
    )
    row = {r.code: r for r in _merged(kind).rows}[PRICE_FEED_STALE]
    assert row.rule.max_attempts == MAX_RECORDED_ATTEMPTS


def test_a_layer_and_a_venue_profile_are_still_hashable() -> None:
    """A frozen value object keeps its hash although its changes are a read-only mapping."""
    assert hash(COMMON_LAYER) == hash(COMMON_LAYER)
    assert hash(venue_profile_of(TradingVenue.SPOT_MAINNET)) is not None
