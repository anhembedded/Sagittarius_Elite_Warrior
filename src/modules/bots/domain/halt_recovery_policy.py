"""`EPIC-042B` — which halts recover by themselves, as layers of plain data (ADR 042 §2.3).

A halt is *transient* when the effective policy has a rule for its reason: the bot then
waits in `AWAITING_RECOVERY` and resumes by itself once the cause has stayed clear for the
rule's dwell. The policy is not a class hierarchy. It is three `RecoveryLayer`s folded in a
fixed order, so every layer and the merged result are values a test can compare and the
effective table can be printed:

  · the **common** layer (`COMMON_LAYER`): the reasons any bot shares and the default rule;
  · the **kind** layer (`IBotKind.recovery_layer`): reasons only that kind has, and changes
    to a common one;
  · the **venue** layer (`VenueProfile.recovery_layer`): the same, per market.

@par The merge rule
Fold common, kind, venue over an empty table. A layer, in this order: (1) when
`clears_lower_layers`, empties the table; (2) removes every code in `withdrawn`; (3) for
each entry of `changes`, takes the existing rule — or, for a code not in the table, the
default rule — and replaces the fields the change sets. The layer that last touched a code
is its `decided_by`. Later layers win. A merged rule is validated when it is built, so a
bad layer fails in a unit test and not at a halt.

@par Extension cases
  · a new common reason — one entry in `COMMON_LAYER` and a probe;
  · a reason only one kind has (the Grid's rate limit, `EPIC-042F`) — one entry in that
    kind's layer;
  · opening Futures — delete `clears_lower_layers` from its venue layer;
  · another dwell for one reason on one venue — a `RuleChange` in that venue's layer.
`tests/unit/modules/bots/domain/test_halt_recovery_policy.py` locks the merge and the
precedence; the attempts a rule allows are counted in `recovery_ledger.py`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import NewType

#: The stable name of a halt reason as the bot record spells it (`GridReason.value`).
HaltCode = NewType("HaltCode", str)

#: The most attempts a bot's record keeps (`recovery_ledger.recorded` caps the list here so the
#: file does not grow). A rule may not allow more than the ledger can hold: with a larger
#: `max_attempts` the oldest entries would fall off and the budget would never run out.
MAX_RECORDED_ATTEMPTS = 16

PRICE_FEED_STALE = HaltCode("price_feed_stale")
USER_STREAM_DOWN = HaltCode("user_stream_down")


@dataclass(frozen=True, slots=True)
class HaltRecoveryRule:
    """What makes one halt reason transient."""

    #: How long the cause must stay clear, continuously, before an attempt.
    dwell: timedelta
    #: The most attempts one bot may make inside `window`, counting every reason.
    max_attempts: int
    #: The rolling window the attempts are counted in.
    window: timedelta
    #: How long the bot may wait before it tells the owner it is still waiting (D11).
    stalled_after: timedelta

    def __post_init__(self) -> None:
        if self.dwell <= timedelta(0):
            raise ValueError("a recovery rule needs a positive dwell")
        if not 1 <= self.max_attempts <= MAX_RECORDED_ATTEMPTS:
            raise ValueError(
                f"a recovery rule allows 1 to {MAX_RECORDED_ATTEMPTS} attempts, "
                f"the most the bot record keeps; got {self.max_attempts}"
            )
        if self.window <= timedelta(0):
            raise ValueError("a recovery rule needs a positive window")
        if self.stalled_after <= self.dwell:
            raise ValueError(
                "a bot is stalled only after it has waited longer than the dwell"
            )


#: The rule a reason has when a layer adds it without saying more (ADR 042 D1, D11).
DEFAULT_RULE = HaltRecoveryRule(
    dwell=timedelta(seconds=120),
    max_attempts=3,
    window=timedelta(hours=24),
    stalled_after=timedelta(minutes=15),
)


@dataclass(frozen=True, slots=True)
class RuleChange:
    """The fields a layer sets on a rule; a field left `None` keeps what the layers below say."""

    dwell: timedelta | None = None
    max_attempts: int | None = None
    window: timedelta | None = None
    stalled_after: timedelta | None = None

    def applied_to(self, rule: HaltRecoveryRule) -> HaltRecoveryRule:
        return HaltRecoveryRule(
            dwell=rule.dwell if self.dwell is None else self.dwell,
            max_attempts=(
                rule.max_attempts if self.max_attempts is None else self.max_attempts
            ),
            window=rule.window if self.window is None else self.window,
            stalled_after=(
                rule.stalled_after if self.stalled_after is None else self.stalled_after
            ),
        )


@dataclass(frozen=True, slots=True)
class RecoveryLayer:
    """One level of the policy: what it removes, and what it adds or tunes."""

    name: str
    #: The layer says "nothing below me recovers": Futures, until its halt may.
    clears_lower_layers: bool = False
    withdrawn: frozenset[HaltCode] = frozenset()
    #: Left out of the hash (the mapping is read-only but unhashable); equality still compares it.
    changes: Mapping[HaltCode, RuleChange] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        both = self.withdrawn & self.changes.keys()
        if both:
            raise ValueError(
                f"layer {self.name!r} both withdraws and changes {sorted(both)}"
            )
        object.__setattr__(self, "changes", MappingProxyType(dict(self.changes)))


#: The reasons any bot shares. Both are a feed or a stream going quiet: a cause outside
#: the bot, a probe can see it clear, and the Resume path rebuilds from exchange evidence.
COMMON_LAYER = RecoveryLayer(
    "common",
    changes={PRICE_FEED_STALE: RuleChange(), USER_STREAM_DOWN: RuleChange()},
)


@dataclass(frozen=True, slots=True)
class EffectiveRule:
    """One row of the merged policy: a reason, its rule, and the layer that decided it."""

    code: HaltCode
    rule: HaltRecoveryRule
    decided_by: str


@dataclass(frozen=True, slots=True)
class EffectivePolicy:
    """The merged policy: the rows, ordered by code, ready to print and to ask."""

    rows: tuple[EffectiveRule, ...]

    def rule_for(self, code: HaltCode) -> HaltRecoveryRule | None:
        for row in self.rows:
            if row.code == code:
                return row.rule
        return None

    @property
    def recovers_nothing(self) -> bool:
        return not self.rows

    @property
    def longest_window(self) -> timedelta:
        return max((row.rule.window for row in self.rows), default=timedelta(0))


def effective_policy(
    common: RecoveryLayer, kind: RecoveryLayer, venue: RecoveryLayer
) -> EffectivePolicy:
    """The three layers merged (ADR 042 §2.3): the one function the director and `bot show` share."""
    table: dict[HaltCode, EffectiveRule] = {}
    for layer in (common, kind, venue):
        if layer.clears_lower_layers:
            table.clear()
        for code in layer.withdrawn:
            table.pop(code, None)
        for code, change in layer.changes.items():
            existing = table.get(code)
            base = existing.rule if existing is not None else DEFAULT_RULE
            table[code] = EffectiveRule(code, change.applied_to(base), layer.name)
    return EffectivePolicy(tuple(table[code] for code in sorted(table)))
