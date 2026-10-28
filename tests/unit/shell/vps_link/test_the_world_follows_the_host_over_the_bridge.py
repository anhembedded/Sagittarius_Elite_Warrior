"""`EPIC-047E` - the VPS tab's picture of its host, kept from the real bridge session.

The business promise (decision record 2026-10-27, D5): what the host published is what the tab holds; a change on the
host reaches it as an event; a cut link leaves the last picture on screen, marked disconnected, and the next welcome
corrects it from the host's snapshot.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    HostFileState,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsLook,
    FactsState,
    Wired,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsTabWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    FACTS_ROOT,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_facts,
)


def test_the_first_snapshot_fills_the_bots_and_the_host_files(tab: VpsTabWorld) -> None:
    world = tab.world.current()

    assert world.connected
    assert [bot.bot_id for bot in world.bots] == sorted(
        [full_bot().bot_id, minimal_bot().bot_id]
    )
    assert world.held == full_host_facts().facts
    assert world.reads is not None
    assert world.last_frame_at is not None


def test_a_bot_written_on_the_host_arrives_as_an_event(tab: VpsTabWorld) -> None:
    from dataclasses import replace

    from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
        BotLifecycleState,
    )

    stopped = replace(full_bot(), state=BotLifecycleState.STOPPED)
    tab.host.bots.put(stopped)

    tab.wait_bot_changed()

    held = {bot.bot_id: bot for bot in tab.world.current().bots}
    assert held[stopped.bot_id].state is BotLifecycleState.STOPPED
    assert (stopped.bot_id, False) in tab.changed


def test_a_bot_deleted_on_the_host_leaves_the_list(tab: VpsTabWorld) -> None:
    tab.host.bots.remove(minimal_bot().bot_id)

    tab.wait_bot_changed()

    assert minimal_bot().bot_id not in [b.bot_id for b in tab.world.current().bots]
    assert (minimal_bot().bot_id, True) in tab.changed


def test_a_cut_keeps_the_last_picture_and_marks_it_disconnected() -> None:
    tab = VpsTabWorld(hold_after_cut=True).start()
    before = tab.world.current()
    heard = before.last_frame_at

    tab.cut()
    tab.wait_down()

    after = tab.world.current()
    tab.stop()
    assert not after.connected
    assert after.bots == before.bots
    assert after.held == before.held
    assert after.last_frame_at == heard


def test_the_next_welcome_corrects_what_changed_while_the_link_was_down(
    tab: VpsTabWorld,
) -> None:
    tab.cut()
    tab.wait_down()
    tab.host.bots.remove(minimal_bot().bot_id)

    tab.wait_up()

    world = tab.world.current()
    assert world.connected
    assert [bot.bot_id for bot in world.bots] == [full_bot().bot_id]


def test_a_host_that_stops_writing_its_facts_is_marked_quiet_while_the_link_lives(
    tab: VpsTabWorld,
) -> None:
    quiet = FactsLook(
        FactsState.STALE,
        revision=41,
        age_s=50.0,
        document=Wired(FACTS_ROOT, full_host_facts()),
    )
    tab.drain_file_changes()

    tab.host.facts.look_now = quiet
    tab.wait_file_changed()

    world = tab.world.current()
    assert world.connected
    assert world.held_file.state is HostFileState.STALE
    assert world.held_file.age_s == 50.0
    assert world.held == full_host_facts().facts  # the last picture is kept, and marked
