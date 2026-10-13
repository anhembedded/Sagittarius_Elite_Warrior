"""The alerting section of the health snapshot (`EPIC-038C`): is anything stuck?"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    DEGRADED,
    REASON_KEY,
    STATUS_KEY,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alerting_health_contributor import (
    SECTION_NAME,
    AlertingHealthContributor,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    build_rig,
)


def test_an_empty_outbox_is_well(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    contributor = AlertingHealthContributor(rig.outbox, rig.clock)

    assert contributor.name == SECTION_NAME == "alerting"
    assert dict(contributor.snapshot()) == {
        "undelivered": 0,
        "oldest_undelivered_age_s": None,
    }


def test_a_waiting_alert_is_counted_and_aged_but_not_yet_a_problem(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.hub.publish(an_alert())
    rig.clock.advance(timedelta(minutes=14))

    snapshot = AlertingHealthContributor(rig.outbox, rig.clock).snapshot()

    assert snapshot["undelivered"] == 1
    assert snapshot["oldest_undelivered_age_s"] == 14 * 60
    assert STATUS_KEY not in snapshot


def test_an_alert_stuck_for_fifteen_minutes_makes_the_section_degraded(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.hub.publish(an_alert())
    rig.clock.advance(timedelta(minutes=15, seconds=1))

    snapshot = AlertingHealthContributor(rig.outbox, rig.clock).snapshot()

    assert snapshot[STATUS_KEY] == DEGRADED
    assert "waiting" in str(snapshot[REASON_KEY])


def test_a_delivered_alert_is_no_longer_a_backlog(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.hub.publish(an_alert())
    rig.deliver_all()
    rig.clock.advance(timedelta(hours=1))

    snapshot = AlertingHealthContributor(rig.outbox, rig.clock).snapshot()

    assert snapshot["undelivered"] == 0
    assert STATUS_KEY not in snapshot
