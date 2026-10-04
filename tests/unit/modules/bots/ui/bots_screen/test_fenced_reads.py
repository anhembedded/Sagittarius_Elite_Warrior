"""`EPIC-029F` — a newer read of a kind supersedes the older one, whose late
answer is dropped (`async-ui-action-rule.md` §1)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

from .bots_screen_fixtures import HeldPool


def _reads(pool: HeldPool) -> tuple[FencedReads, list[tuple[object, str, object]]]:
    reads = FencedReads(pool, {kind: ActionOwnershipTracker() for kind in ReadKind})
    heard: list[tuple[object, str, object]] = []
    reads.answered.connect(
        lambda kind, label, answer: heard.append((kind, label, answer))
    )
    reads.failed.connect(lambda kind, label, error: heard.append((kind, label, error)))
    return reads, heard


def test_an_older_read_answering_last_is_dropped(qapp) -> None:
    pool = HeldPool()
    reads, heard = _reads(pool)
    reads.read(ReadKind.LIST, "", lambda: "older")
    reads.read(ReadKind.LIST, "", lambda: "newer")

    pool.run(1)
    pool.run(0)

    assert heard == [(ReadKind.LIST, "", "newer")]


def test_reads_of_different_kinds_do_not_supersede_each_other(qapp) -> None:
    pool = HeldPool()
    reads, heard = _reads(pool)
    reads.read(ReadKind.PLANNER, "a00001", lambda: "market")
    reads.read(ReadKind.FILLS, "a00001", lambda: "fills")

    pool.run_all()

    assert [answer for _, _, answer in heard] == ["market", "fills"]


def test_a_failed_read_is_named_in_words_and_dropped_reads_say_nothing(qapp) -> None:
    pool = HeldPool()
    reads, heard = _reads(pool)

    def broken() -> object:
        raise TimeoutError("venue slow")

    reads.read(ReadKind.FILLS, "a00001", broken)
    pool.run_all()
    reads.read(ReadKind.LIST, "", lambda: "late")
    reads.drop_all()
    pool.run_all()

    assert heard == [(ReadKind.FILLS, "a00001", "venue slow")]
