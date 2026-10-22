"""`EPIC-045G` - what a person reads of a HALTED bot's resume proposal, and the token that names it.

A resume proposes a ladder and places nothing; a person reads it and confirms (decision D13). On the
running host the reading and the confirming are two command files, so the confirmation names what was
read: `fingerprint` is a short digest of the proposal's price, inventory and orders. A second resume
re-proposes at its own price, the fingerprint changes, and a confirmation that carries the old one lays
nothing (owner decision O3, from the review of #708). The Bots tab's Confirm resume names none: one
person sees and confirms there.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: How many hex characters of the digest a person types: enough to tell two proposals apart, short enough to read aloud.
FINGERPRINT_LENGTH = 8


@dataclass(frozen=True, slots=True)
class ResumeProposalSummary:
    """The proposal as the operator is shown it."""

    #: The digest a confirmation must repeat.
    fingerprint: str
    #: How many orders the ladder lays.
    orders: int
    #: The price the ladder was drawn from.
    price: Decimal
    #: The base the bot holds, which the SELL side was sized to.
    held: Decimal
    #: Which proposal this is, in the order the process made them: every resume that proposes makes a
    #: newer one, even over an identical ladder, so a caller that read one before asking for another can
    #: tell the new proposal from the one that was already held. Not part of the fingerprint.
    sequence: int = 0
