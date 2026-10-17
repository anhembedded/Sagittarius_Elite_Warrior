"""`EPIC-042C` - which event a halt applies: a plain `halt`, or `halt_transient` (ADR 042 §2.1).

The lifecycle table says what each event does; it cannot say *whether this halt is one the bot
may recover from by itself*. That depends on the reason (the effective policy has a rule for it),
on the state the bot halts from, and on the bot's budget. This is the one place that asks.

  · only RUNNING and STARTING halt transiently (D8): the owner's Pause is never undone by a
    machine, and a RECOVERING bot has no open order session, so a recovery could not run;
  · a reason the policy has no rule for halts plainly: a person must look;
  · a reason with a rule but no budget left halts plainly **and says so**, so the `BOT_HALTED`
    alert reads "the 3 automatic recoveries of the last 24 h are used up".

Pure: it reads the bot and the policy and answers; `BotRunState.halt` applies the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    EffectivePolicy,
    HaltCode,
    HaltRecoveryRule,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    budget_left,
)

#: The states a transient halt may leave (D8).
TRANSIENT_FROM: frozenset[BotLifecycleState] = frozenset(
    {BotLifecycleState.RUNNING, BotLifecycleState.STARTING}
)


@dataclass(frozen=True, slots=True)
class HaltDecision:
    """What a halt applies, and what it adds to the reason when the budget is spent."""

    event: BotLifecycleEvent
    #: Words appended to the halt's detail; empty unless the budget is what made it plain.
    note: str = ""
    #: The rule the halt was judged against, when it has one.
    rule: HaltRecoveryRule | None = None


class HaltRecoveryDirector:
    """Judges a halt against one bot's effective policy."""

    def __init__(self, policy: EffectivePolicy) -> None:
        self._policy = policy

    @property
    def keep_for(self) -> timedelta:
        """How long the ledger must keep an attempt: the longest window any rule counts in."""
        return self._policy.longest_window

    @property
    def codes(self) -> tuple[HaltCode, ...]:
        """Every reason this bot may recover from: all of them must be clear before it resumes."""
        return self._policy.codes

    def rule_for(self, code: HaltCode) -> HaltRecoveryRule | None:
        return self._policy.rule_for(code)

    def decide(self, bot: Bot, code: HaltCode, now: datetime) -> HaltDecision:
        rule = self._policy.rule_for(code)
        if rule is None or bot.state not in TRANSIENT_FROM:
            return HaltDecision(BotLifecycleEvent.HALT)
        attempts = bot.lifecycle.recovery_attempts
        if not budget_left(rule, attempts, now):
            return HaltDecision(
                BotLifecycleEvent.HALT, budget_used_up_words(rule), rule
            )
        return HaltDecision(BotLifecycleEvent.HALT_TRANSIENT, rule=rule)


def budget_used_up_words(rule: HaltRecoveryRule) -> str:
    """The sentence a bot gives when its automatic recoveries are spent."""
    hours = rule.window.total_seconds() / 3600
    return (
        f"the {rule.max_attempts} automatic recoveries allowed in {hours:g} h are used up; "
        "resume by hand"
    )


#: A bot whose policy recovers nothing: every halt is plain. The default of `BotRunState`.
NO_HALT_RECOVERY = HaltRecoveryDirector(EffectivePolicy(()))
