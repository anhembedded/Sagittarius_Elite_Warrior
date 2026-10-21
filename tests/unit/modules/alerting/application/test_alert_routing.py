"""Which channel hears an alert, and how loudly (N4, N5, N8)."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    bot_subject,
    build_rig,
)


def test_critical_goes_to_two_channels_when_two_are_enabled(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    assert [len(c.received) for c in rig.channels.values()] == [1, 1]
    assert {item.loudness for c in rig.channels.values() for item in c.received} == {
        Loudness.LOUD
    }


def test_critical_still_reaches_a_second_channel_when_the_routes_name_only_one(
    tmp_path: Path,
) -> None:
    """N8 over a cell turned off: the second channel is the cover for a push
    that never arrives, so the matrix cannot remove it."""
    rig = build_rig(tmp_path, channel_ids=("phone", "backup", "pager"))
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.BOT_EVENTS, "backup", Loudness.OFF),
                AlertRoute(AlertGroup.BOT_EVENTS, "pager", Loudness.OFF),
            )
        )
    )

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    reached = [cid for cid, c in rig.channels.items() if c.received]
    assert len(reached) == 2
    assert "phone" in reached


def test_one_channel_alone_is_enough_when_only_one_is_configured(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    assert len(rig.channels["phone"].received) == 1


def test_a_disabled_channel_is_never_used_not_even_for_critical(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone", "backup", "pager"))
    rig.settings.replace(AlertSettings(disabled_channels=frozenset({"pager"})))

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    assert rig.channels["pager"].received == []
    assert (
        len(rig.channels["phone"].received) == len(rig.channels["backup"].received) == 1
    )


def test_a_silent_cell_sends_silently_and_an_off_cell_sends_nothing(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.NOTICES, "phone", Loudness.SILENT),
                AlertRoute(AlertGroup.NOTICES, "backup", Loudness.OFF),
            )
        )
    )

    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))
    rig.deliver_all()

    [sent] = rig.channels["phone"].received
    assert sent.loudness is Loudness.SILENT
    assert rig.channels["backup"].received == []


def test_a_bot_set_to_critical_only_drops_its_warnings(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.settings.replace(
        AlertSettings(bot_modes={"g3n092": BotAlertMode.CRITICAL_ONLY})
    )

    rig.hub.publish(an_alert(AlertKind.RANGE_EXIT))
    rig.hub.publish(an_alert(AlertKind.RANGE_EXIT, bot_subject("other")))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    subjects = [
        (i.alert.kind, i.alert.subject.bot_id) for i in rig.channels["phone"].received
    ]
    assert subjects == [
        (AlertKind.BOT_HALTED, "g3n092"),
        (AlertKind.RANGE_EXIT, "other"),
    ]


def test_a_bot_set_to_off_sends_nothing_and_leaves_the_others_alone(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.settings.replace(AlertSettings(bot_modes={"g3n092": BotAlertMode.OFF}))

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject("other")))
    rig.deliver_all()

    [sent] = rig.channels["phone"].received
    assert sent.alert.subject.bot_id == "other"
    assert len(rig.outbox.history(10)) == 2  # the muted one is still on record


def test_a_second_channel_needs_no_application_change(tmp_path: Path) -> None:
    """Composition alone adds a channel: the same hub and worker serve one, two
    or three fakes of different behaviour."""
    one = build_rig(tmp_path / "one", channel_ids=("phone",))
    three = build_rig(tmp_path / "three", channel_ids=("phone", "backup", "pager"))

    for rig in (one, three):
        rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
        rig.deliver_all()

    assert [len(c.received) for c in one.channels.values()] == [1]
    assert [len(c.received) for c in three.channels.values()] == [1, 1, 1]


def test_a_critical_is_loud_somewhere_even_if_the_matrix_makes_every_cell_silent(
    tmp_path: Path,
) -> None:
    """Review of PR #670: Silent on every channel for the group would let a halt arrive without a
    sound. The router keeps one loud delivery for a CRITICAL, as it keeps a second channel."""
    rig = build_rig(tmp_path)
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.BOT_EVENTS, "phone", Loudness.SILENT),
                AlertRoute(AlertGroup.BOT_EVENTS, "backup", Loudness.SILENT),
            )
        )
    )

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    loudness = [item.loudness for c in rig.channels.values() for item in c.received]
    assert len(loudness) == 2
    assert loudness.count(Loudness.LOUD) == 1
    assert loudness.count(Loudness.SILENT) == 1


def test_a_critical_already_loud_somewhere_keeps_its_other_cell_silent(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.BOT_EVENTS, "phone", Loudness.LOUD),
                AlertRoute(AlertGroup.BOT_EVENTS, "backup", Loudness.SILENT),
            )
        )
    )

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    assert [i.loudness for i in rig.channels["phone"].received] == [Loudness.LOUD]
    assert [i.loudness for i in rig.channels["backup"].received] == [Loudness.SILENT]


def test_a_warning_may_be_silent_everywhere(tmp_path: Path) -> None:
    """Only a CRITICAL has a loud floor: the owner's Silent for the rest is kept."""
    rig = build_rig(tmp_path)
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.NOTICES, "phone", Loudness.SILENT),
                AlertRoute(AlertGroup.NOTICES, "backup", Loudness.SILENT),
            )
        )
    )

    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))
    rig.deliver_all()

    assert {i.loudness for c in rig.channels.values() for i in c.received} == {
        Loudness.SILENT
    }
