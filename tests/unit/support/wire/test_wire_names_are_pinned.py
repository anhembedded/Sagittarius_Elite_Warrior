"""`EPIC-047A` — a wire name is a contract: the whole list is written down here, so renaming one is a
decision in a diff and not a side effect of a refactor.

A round-trip test cannot see a rename (both sides move together); the handshake would refuse every
desktop with a renamed root. Changing this list is the version change: an incompatible wire form
takes a new name ending `/2`, and the old name is not reused.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots

PINNED = (
    "sew.bot-command-result/1",
    "sew.bot-fills/1",
    "sew.bot-list/1",
    "sew.bot-readiness/1",
    "sew.bot-run-facts/1",
    "sew.bot-snapshot/1",
    "sew.candle-window/1",
    "sew.connect-failure/1",
    "sew.connection-read/1",
    "sew.exchange-checking/1",
    "sew.exchange-facts/1",
    "sew.exchange-loaded/1",
    "sew.exchange-unavailable/1",
    "sew.futures-loaded/1",
    "sew.host-control-reply/1",
    "sew.host-control-request/1",
    "sew.host-facts-document/1",
    "sew.host-reads-document/1",
    "sew.market-data-document/1",
    "sew.plan-risk-facts/1",
    "sew.plan-risk-read/1",
    "sew.plan-risk-unavailable/1",
    "sew.planner-market/1",
    "sew.venue-account-snapshot/1",
    "sew.venue-connection/1",
    "sew.venue-snapshot/1",
)


def test_the_wire_names_this_build_carries_are_the_pinned_list() -> None:
    assert link_roots().wire_names() == PINNED
