"""`EPIC-036B2` — a bot's reason decides which alert the owner gets, and every reason is routed on
purpose.

The rate limit, a rejected key and a state file that cannot be saved reached the owner as a
generic halt, or (the storage pause) not at all; a price feed that stays quiet reached them as a
generic "recovery stalled". Each is now a kind of its own, with a fixed sentence that carries no
text from the exchange or the disk.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    CLEARED_ON_ENTRY,
    EXIT_ON_STOP,
    BotAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_reason_routes import (
    REASON_ROUTES,
    Disposition,
    ReasonRoute,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    KIND_PROFILES,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    SPOT,
    an_alert,
    bot_subject,
    build_rig,
)

#: What the failing call wrote - a credential-looking string must never reach an alert.
_LEAK = "apiKey=AKIAXXXXXXXX-secret-fragment path=/home/owner/state/bot.json"


def _source(bots: Bots) -> tuple[BotAlertSource, RecordingAlertPublisher]:
    published = RecordingAlertPublisher()
    source = BotAlertSource(bots, published, FakeAlertClock())
    source.seed()
    return source, published


def _changed() -> BotChangedEvent:
    return BotChangedEvent(bot_id=BOT)


def _key(kind: AlertKind) -> str:
    subject = AlertSubject.bot(BOT, "eth-grid", "grid", "spot_mainnet", "ETHUSDT")
    return Alert.condition_key(kind, subject)


def _enter(state: str, reason: str, detail: str = "") -> list[Alert]:
    bots = Bots(entry("RUNNING"))
    source, published = _source(bots)
    bots.move(state, reason, detail)
    source.on_bot_changed(_changed())
    return published.published


# --- the table is complete -------------------------------------------------------------------


def test_every_bot_reason_code_is_routed_on_purpose() -> None:
    """A new `GridReason` that is not a row fails here, so it cannot silently alert wrongly."""
    assert set(REASON_ROUTES) == {reason.value for reason in GridReason}


def test_the_exit_routes_agree_with_the_stop_path() -> None:
    exits = {
        code: route.kind
        for code, route in REASON_ROUTES.items()
        if route.disposition is Disposition.EXIT
    }
    assert exits == {
        **EXIT_ON_STOP,
        "protective_stop_triggered": AlertKind.STOP_LOSS_HIT,
    }


def test_every_kind_a_route_names_is_in_the_catalog() -> None:
    kinds = {route.kind for route in REASON_ROUTES.values() if route.kind is not None}
    assert kinds <= set(KIND_PROFILES)


def test_every_state_a_route_names_is_a_lifecycle_state() -> None:
    states = {state for route in REASON_ROUTES.values() for state in route.states}
    assert states <= {state.value for state in BotLifecycleState}


def test_every_kind_a_route_raises_is_ended_by_a_return_to_running() -> None:
    raised = {
        route.kind
        for route in REASON_ROUTES.values()
        if route.disposition in (Disposition.OWN_KIND, Disposition.STALLED)
    }
    assert raised <= set(CLEARED_ON_ENTRY["RUNNING"])


def test_a_route_that_names_a_kind_and_no_text_cannot_be_built() -> None:
    with pytest.raises(ValueError):
        ReasonRoute.own(AlertKind.RATE_LIMITED, frozenset({"HALTED"}), "")
    with pytest.raises(ValueError):
        ReasonRoute(Disposition.GENERIC, AlertKind.BOT_HALTED)
    with pytest.raises(ValueError):
        ReasonRoute(Disposition.EXIT)


@pytest.mark.parametrize(
    "code",
    [
        code
        for code, route in REASON_ROUTES.items()
        if route.disposition is not Disposition.EXIT
    ],
)
def test_a_halt_for_any_reason_is_the_alert_its_route_says(code: str) -> None:
    """Behaviour per row: the entry into HALTED with each routed reason."""
    route = REASON_ROUTES[code]
    alerts = _enter("HALTED", code)

    if route.disposition is Disposition.SILENT:
        # A note is never a halt; were one to arrive on a halt it still must not be lost.
        assert [a.kind for a in alerts] == [AlertKind.BOT_HALTED]
    elif route.disposition is Disposition.OWN_KIND and "HALTED" in route.states:
        assert [a.kind for a in alerts] == [route.kind]
    else:
        assert [a.kind for a in alerts] == [AlertKind.BOT_HALTED]


def test_a_reason_the_table_does_not_know_is_a_generic_halt() -> None:
    """`test_a_new_bot_kind_needs_no_change_in_alerting`: its own reason is the generic kind."""
    assert [a.kind for a in _enter("HALTED", "a_reason_of_a_new_kind")] == [
        AlertKind.BOT_HALTED
    ]


# --- RATE_LIMITED, KEY_REJECTED, STORAGE_FAILURE ---------------------------------------------


def test_a_wait_for_the_exchanges_pause_that_stalled_is_one_warning_that_says_it_resumes() -> (
    None
):
    """`EPIC-042F`: a pause is waited out in AWAITING_RECOVERY (silent on entry); when that wait
    stalls the ladder is still resting, and the bot does resume by itself when the pause ends."""
    bots = Bots(entry("AWAITING_RECOVERY", "rate_limited"))
    source, published = _source(bots)

    source.on_recovery_stalled(
        BotRecoveryStalledEvent(bot_id=BOT, reason="rate_limited", waited_s=900)
    )

    [alert] = published.published
    assert alert.kind is AlertKind.RATE_LIMITED
    assert alert.severity is Severity.WARNING
    assert "resumes by itself" in alert.detail
    assert "still resting on the exchange" in alert.detail
    assert alert.dedup_key == _key(AlertKind.RATE_LIMITED)


def test_a_rate_limit_that_is_a_plain_halt_is_the_critical_halt_and_never_says_it_resumes() -> (
    None
):
    """A pause too long to wait, or a used-up budget, leaves the bot HALTED for a person to resume;
    an alert that said "resumes by itself" there would be false (review of PR #622)."""
    [alert] = _enter(
        "HALTED",
        "rate_limited",
        f"the pause is too long to wait ({_LEAK}); resume by hand",
    )

    assert alert.kind is AlertKind.BOT_HALTED
    assert alert.severity is Severity.CRITICAL
    assert "resumes by itself" not in alert.detail
    assert "resume by hand" in alert.detail


@pytest.mark.parametrize("state", ["HALTED", "ERROR"])
def test_a_rejected_key_is_one_critical_alert_that_says_orders_may_rest(
    state: str,
) -> None:
    [alert] = _enter(state, "key_rejected", f"the exchange said ({_LEAK})")

    assert alert.kind is AlertKind.KEY_REJECTED
    assert alert.severity is Severity.CRITICAL
    assert "may still rest on the exchange" in alert.detail
    assert "cannot cancel them" in alert.detail


def test_a_bot_paused_by_its_storage_is_one_critical_alert() -> None:
    [alert] = _enter("PAUSED", "storage_failure", f"cannot be saved: {_LEAK}")

    assert alert.kind is AlertKind.STORAGE_FAILURE
    assert alert.severity is Severity.CRITICAL
    assert "press Resume" in alert.detail
    assert "orders rest on the exchange" in alert.detail


def test_a_pause_the_owner_asked_for_is_still_silent() -> None:
    assert _enter("PAUSED", "") == []
    assert _enter("PAUSED", "restored_paused") == []


@pytest.mark.parametrize(
    ("reason", "state"),
    [
        ("key_rejected", "HALTED"),
        ("key_rejected", "ERROR"),
        ("storage_failure", "PAUSED"),
    ],
)
def test_no_text_from_the_exchange_or_the_disk_reaches_an_alert(
    reason: str, state: str
) -> None:
    [alert] = _enter(state, reason, _LEAK)

    for text in (alert.title, alert.detail):
        assert "AKIA" not in text
        assert "secret-fragment" not in text
        assert "/home/owner" not in text


@pytest.mark.parametrize(
    ("reason", "state", "kind"),
    [
        ("key_rejected", "HALTED", AlertKind.KEY_REJECTED),
        ("storage_failure", "PAUSED", AlertKind.STORAGE_FAILURE),
    ],
)
def test_the_return_to_running_ends_the_condition(
    reason: str, state: str, kind: AlertKind
) -> None:
    bots = Bots(entry("RUNNING"))
    source, published = _source(bots)
    bots.move(state, reason)
    source.on_bot_changed(_changed())
    assert _key(kind) not in published.cleared

    bots.move("RUNNING")
    source.on_bot_changed(_changed())

    assert _key(kind) in published.cleared


def test_a_second_halt_of_another_reason_is_a_new_alert() -> None:
    bots = Bots(entry("RUNNING"))
    source, published = _source(bots)
    bots.move("PAUSED", "storage_failure")
    source.on_bot_changed(_changed())
    bots.move("RUNNING")
    source.on_bot_changed(_changed())

    bots.move("HALTED", "key_rejected")
    source.on_bot_changed(_changed())

    assert [a.kind for a in published.published] == [
        AlertKind.STORAGE_FAILURE,
        AlertKind.KEY_REJECTED,
    ]


# --- PRICE_FEED_STALE ------------------------------------------------------------------------


def test_a_wait_on_a_quiet_price_feed_is_silent_on_entry_and_one_critical_alert_when_it_stalls() -> (
    None
):
    bots = Bots(entry("RUNNING"))
    source, published = _source(bots)

    bots.move("AWAITING_RECOVERY", "price_feed_stale", f"last tick 70 s ago {_LEAK}")
    source.on_bot_changed(_changed())
    assert published.published == [], "entering a wait is silent (EPIC-042 D11)"

    source.on_recovery_stalled(
        BotRecoveryStalledEvent(bot_id=BOT, reason="price_feed_stale", waited_s=900)
    )

    [alert] = published.published
    assert alert.kind is AlertKind.PRICE_FEED_STALE
    assert alert.severity is Severity.CRITICAL
    assert alert.title == "Price feed stale: eth-grid"
    assert "15 minute(s)" in alert.detail
    assert "stop loss" in alert.detail
    assert "secret-fragment" not in alert.detail
    assert alert.dedup_key == _key(AlertKind.PRICE_FEED_STALE)


def test_a_halt_for_a_quiet_feed_stays_the_halt_with_its_recoveries_line() -> None:
    """The halt that says the automatic recoveries are used up is the owner's call to act on."""
    [alert] = _enter(
        "HALTED", "price_feed_stale", "the 3 automatic recoveries are used up"
    )

    assert alert.kind is AlertKind.BOT_HALTED
    assert "the 3 automatic recoveries are used up" in alert.detail


def test_the_feed_coming_back_ends_the_condition() -> None:
    bots = Bots(entry("AWAITING_RECOVERY", "price_feed_stale"))
    source, published = _source(bots)
    source.on_recovery_stalled(
        BotRecoveryStalledEvent(bot_id=BOT, reason="price_feed_stale", waited_s=900)
    )

    bots.move("RUNNING")
    source.on_bot_changed(_changed())

    assert _key(AlertKind.PRICE_FEED_STALE) in published.cleared


def test_twenty_bots_losing_the_feed_become_one_grouped_alert(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    for number in range(20):
        rig.hub.publish(
            an_alert(AlertKind.PRICE_FEED_STALE, bot_subject(f"bot{number}"))
        )
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    [grouped] = [item.alert for item in rig.channels["phone"].received]
    assert grouped.kind is AlertKind.PRICE_FEED_STALE
    assert "20 bots" in grouped.title
    assert SPOT in grouped.title


def test_a_bots_stalled_feed_is_hidden_by_its_venues_stream_outage_through_the_real_hub(
    tmp_path: Path,
) -> None:
    """The source's alert, not a hand-made one, carries the subject the hub inhibits on."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    bots = Bots(entry("AWAITING_RECOVERY", "price_feed_stale"))
    source = BotAlertSource(bots, rig.hub, rig.clock)
    source.seed()
    # The bot's venue as the status report spells it, which is how `StreamAlertSource` names it.
    venue_down = an_alert(
        AlertKind.USER_STREAM_DOWN, AlertSubject.venue_wide(entry().venue)
    )

    rig.hub.publish(venue_down)
    source.on_recovery_stalled(
        BotRecoveryStalledEvent(bot_id=BOT, reason="price_feed_stale", waited_s=900)
    )
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    assert rig.received_kinds("phone") == [AlertKind.USER_STREAM_DOWN]
    assert rig.hub.suppressed_count(venue_down.dedup_key) == 1
