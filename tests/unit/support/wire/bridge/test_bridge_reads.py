"""`EPIC-047C` - a snapshot, then one event per write to a bot's file, and an order that cannot contradict itself."""

from __future__ import annotations

import json
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    FACTS_LOOK_S,
    POLL_S,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsLook,
    FactsState,
)
from Sagittarius_Elite_Warrior.src.support.wire.revision_gate import RevisionGate
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    Desk,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)


def _subscribed(desk: Desk) -> Desk:
    desk.greet()
    desk.call("subscribe")
    return desk


def _stopped(bot: BotSnapshot) -> BotSnapshot:
    return replace(bot, state=BotLifecycleState.STOPPED)


def test_a_snapshot_carries_every_bot_a_revision_for_each_and_the_hosts_facts() -> None:
    desk = Desk()
    desk.greet()

    data = desk.result_of(desk.call("snapshot"))

    listed = ROOTS.decode(data["list"])
    assert isinstance(listed, BotList)
    assert {b.bot_id for b in listed.bots} == {full_bot().bot_id, minimal_bot().bot_id}
    assert data["revisions"] == {full_bot().bot_id: 1, minimal_bot().bot_id: 1}
    assert data["seq"] == 0
    facts = data["facts"]
    assert isinstance(facts, dict)
    assert (facts["state"], facts["revision"]) == ("live", 41)
    assert ROOTS.schema_of(facts["document"]) == "sew.host-facts-document/1"


def test_a_snapshot_with_no_bots_and_no_facts_file_says_so() -> None:
    desk = Desk()
    desk.bots.remove(full_bot().bot_id)
    desk.bots.remove(minimal_bot().bot_id)
    desk.facts.look_now = FactsLook(FactsState.MISSING, problem="there is no file")
    desk.greet()

    data = desk.result_of(desk.call("snapshot"))

    assert data["revisions"] == {}
    assert data["facts"] == {
        "state": "missing",
        "revision": 0,
        "age_s": None,
        "problem": "there is no file",
        "document": None,
    }


def test_a_write_to_a_bots_file_is_one_event_with_the_new_bot_and_the_next_revision() -> (
    None
):
    desk = _subscribed(Desk())
    desk.bots.put(_stopped(full_bot()))

    desk.advance(POLL_S)

    (event,) = desk.events("bot")
    assert (event["bot_id"], event["revision"], event["seq"]) == (
        full_bot().bot_id,
        2,
        1,
    )
    assert ROOTS.decode(event["bot"]) == _stopped(full_bot())
    assert event["refused"] == ""


def test_an_unchanged_directory_makes_no_event_however_often_it_is_looked_at() -> None:
    desk = _subscribed(Desk())

    for _ in range(5):
        desk.advance(POLL_S)

    assert desk.events("bot") == []


def test_two_writes_between_two_looks_are_one_event_not_two() -> None:
    """The poll sees the directory, not the writes: the spike's p95 of 100 ms is this cadence."""
    desk = _subscribed(Desk())
    desk.bots.put(_stopped(full_bot()))
    desk.bots.put(replace(full_bot(), name="renamed"))

    desk.advance(POLL_S)

    (event,) = desk.events("bot")
    assert ROOTS.decode(event["bot"]).name == "renamed"  # type: ignore[attr-defined]


def test_a_removed_file_is_an_event_with_no_bot_and_a_revision_that_goes_on() -> None:
    desk = _subscribed(Desk())
    desk.bots.remove(minimal_bot().bot_id)

    desk.advance(POLL_S)

    (event,) = desk.events("bot")
    assert (event["bot_id"], event["bot"], event["revision"]) == (
        minimal_bot().bot_id,
        None,
        2,
    )


def test_a_bot_that_comes_back_after_a_removal_does_not_reuse_a_revision() -> None:
    desk = _subscribed(Desk())
    desk.bots.remove(minimal_bot().bot_id)
    desk.advance(POLL_S)
    desk.bots.put(minimal_bot())
    desk.advance(POLL_S)

    revisions = [e["revision"] for e in desk.events("bot")]

    assert revisions == [2, 3]


def test_a_file_that_can_no_longer_be_read_is_an_event_that_says_why() -> None:
    desk = _subscribed(Desk())
    desk.bots.put(full_bot(), refused="unknown schema_version 2")

    desk.advance(POLL_S)

    (event,) = desk.events("bot")
    assert (event["bot"], event["refused"]) == (None, "unknown schema_version 2")


def test_nothing_is_sent_before_the_desk_subscribes_but_the_snapshot_is_current() -> (
    None
):
    desk = Desk()
    desk.greet()
    desk.bots.put(_stopped(full_bot()))
    desk.advance(POLL_S)

    data = desk.result_of(desk.call("snapshot"))

    assert desk.sent("event") == []
    assert data["revisions"][full_bot().bot_id] == 2  # type: ignore[index]
    assert ROOTS.decode(data["list"]).bots[0].state is BotLifecycleState.STOPPED  # type: ignore[attr-defined]


def test_events_come_with_a_sequence_that_only_grows() -> None:
    desk = _subscribed(Desk())
    for _ in range(3):
        desk.bots.put(replace(full_bot(), name=str(desk.now)))
        desk.advance(POLL_S)

    assert [e["seq"] for e in desk.sent("event")] == [1, 2, 3]


def test_a_directory_is_looked_at_no_more_often_than_the_poll_interval() -> None:
    desk = _subscribed(Desk())
    desk.advance(POLL_S)
    before = desk.bots.asked

    desk.advance(POLL_S / 4)
    desk.advance(POLL_S / 4)

    assert desk.bots.asked == before


def test_a_snapshot_and_the_events_that_overtake_it_converge_in_either_order() -> None:
    """The reason for a revision (DERISK R5): the gate keeps the greater one whatever arrives first."""
    desk = _subscribed(Desk())
    snapshot = desk.result_of(desk.call("snapshot"))
    desk.bots.put(_stopped(full_bot()))
    desk.advance(POLL_S)
    (event,) = desk.events("bot")
    in_order, reversed_order = RevisionGate[BotSnapshot](), RevisionGate[BotSnapshot]()

    listed = ROOTS.decode(snapshot["list"]).bots  # type: ignore[attr-defined]
    revisions = snapshot["revisions"]
    for gate, event_first in ((in_order, False), (reversed_order, True)):
        if event_first:
            gate.offer(event["bot_id"], event["revision"], ROOTS.decode(event["bot"]))  # type: ignore[arg-type]
        for bot in listed:
            gate.offer(bot.bot_id, revisions[bot.bot_id], bot)  # type: ignore[index]
        if not event_first:
            gate.offer(event["bot_id"], event["revision"], ROOTS.decode(event["bot"]))  # type: ignore[arg-type]

    assert in_order.value_of(full_bot().bot_id) == _stopped(full_bot())
    assert reversed_order.value_of(full_bot().bot_id) == _stopped(full_bot())


def test_a_new_host_facts_revision_is_one_event_and_the_same_revision_is_none() -> None:
    desk = _subscribed(Desk())
    desk.advance(FACTS_LOOK_S)
    assert desk.events("facts") == []

    desk.facts.host_wrote(42)
    desk.advance(FACTS_LOOK_S)
    desk.advance(FACTS_LOOK_S)

    (event,) = desk.events("facts")
    assert (event["revision"], event["state"]) == (42, "live")
    assert ROOTS.schema_of(event["document"]) == "sew.host-facts-document/1"


def test_a_host_that_goes_quiet_is_an_event_although_the_file_did_not_change() -> None:
    desk = _subscribed(Desk())
    desk.facts.look_now = replace(
        desk.facts.look_now, state=FactsState.STALE, age_s=60.0
    )

    desk.advance(FACTS_LOOK_S)

    (event,) = desk.events("facts")
    assert (event["state"], event["revision"]) == ("stale", 41)


def test_the_facts_the_snapshot_carried_are_not_sent_again_as_an_event() -> None:
    desk = _subscribed(Desk())
    desk.facts.host_wrote(50)
    desk.result_of(desk.call("snapshot"))

    desk.advance(FACTS_LOOK_S)

    assert desk.events("facts") == []


def test_every_message_is_one_line_of_strict_json() -> None:
    desk = _subscribed(Desk())
    desk.result_of(desk.call("snapshot"))
    desk.bots.put(_stopped(full_bot()))
    desk.advance(POLL_S)

    for message in desk.out:
        assert "\n" not in json.dumps(message, allow_nan=False)
