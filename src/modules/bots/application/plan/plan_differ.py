"""What applying a plan would do (`EPIC-038I`): the diff, with nothing touched.

Identity is `name` + `venue`. Whether a stored bot may be edited or deleted is the
lifecycle table's answer (`permits_edit`, `permits_delete`), asked here so the diff says
"needs stop first" before any command is dispatched; the commands still refuse on their
own (the plan path and the screen path are one path). An entry the table refuses does not
stop the others.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
    PlanChange,
    PlanDiff,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    AT_REST_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
    permits_delete,
    permits_edit,
    restarts_into_recovering,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

type Identity = tuple[str, TradingVenue]


class PrunePolicy(str, Enum):
    #: A stored bot the plan does not name is left alone.
    KEEP = "keep"
    #: ... is deleted, if it is at rest.
    PRUNE = "prune"


def diff_plan(
    plan: BotPlanDocument,
    bots: Sequence[BotSnapshot],
    recorded: AppliedPlan | None,
    prune: PrunePolicy,
) -> PlanDiff:
    by_identity: dict[Identity, list[BotSnapshot]] = {}
    for bot in bots:
        by_identity.setdefault((bot.name.strip(), bot.venue), []).append(bot)
    changes = [
        _change_for(entry, by_identity.get(entry.identity, []), recorded)
        for entry in plan.bots
    ]
    named = {entry.identity for entry in plan.bots}
    changes += [
        _unnamed(bot, prune, recorded)
        for bot in bots
        if (bot.name.strip(), bot.venue) not in named
    ]
    return PlanDiff(tuple(changes))


def desired_state_of(bot: BotSnapshot, recorded: AppliedPlan | None) -> DesiredState:
    """What the operator wants of a stored bot now: the record's word, else what it is doing."""
    said = recorded.desired_for(bot.bot_id) if recorded is not None else None
    if said is not None:
        return said
    return (
        DesiredState.RUNNING
        if restarts_into_recovering(bot.state)
        else DesiredState.STOPPED
    )


def _change_for(
    entry: PlannedBot, matches: list[BotSnapshot], recorded: AppliedPlan | None
) -> PlanChange:
    if not matches:
        return PlanChange(
            ChangeAction.CREATE,
            entry.name,
            entry.venue,
            None,
            "a new bot, saved as a DRAFT; "
            + _meaning(entry.desired_state, BotLifecycleState.DRAFT),
            planned=entry,
            desired_after=entry.desired_state,
        )
    if len(matches) > 1:
        ids = ", ".join(sorted(bot.bot_id for bot in matches))
        return _blocked(
            entry,
            None,
            f"{len(matches)} stored bots share this name and venue ({ids}); "
            "a bot is identified by them, so nothing is done for this entry",
        )
    (bot,) = matches
    before = desired_state_of(bot, recorded)
    problem = _cannot_edit_in_place(entry, bot)
    if problem:
        return _blocked(entry, bot, problem, before)
    differing = _differing_params(entry.params, bot.config)
    if differing:
        if not permits_edit(bot.state):
            return _blocked(
                entry,
                bot,
                f"needs stop first: the bot is {bot.state.value} and its parameters "
                f"differ ({', '.join(differing)})",
                before,
            )
        return PlanChange(
            ChangeAction.EDIT,
            entry.name,
            entry.venue,
            bot.bot_id,
            f"parameters change: {'; '.join(differing)}; the bot lands on DRAFT; "
            + _meaning(entry.desired_state, BotLifecycleState.DRAFT),
            planned=entry,
            desired_before=before,
            desired_after=entry.desired_state,
            state=bot.state.value,
        )
    return PlanChange(
        ChangeAction.LEAVE,
        entry.name,
        entry.venue,
        bot.bot_id,
        "matches the plan; " + _meaning(entry.desired_state, bot.state),
        planned=entry,
        desired_before=before,
        desired_after=entry.desired_state,
        state=bot.state.value,
    )


def _unnamed(
    bot: BotSnapshot, prune: PrunePolicy, recorded: AppliedPlan | None
) -> PlanChange:
    before = desired_state_of(bot, recorded)
    base = (bot.name, bot.venue, bot.bot_id)
    if prune is PrunePolicy.KEEP:
        return PlanChange(
            ChangeAction.LEAVE,
            *base[:2],
            bot.bot_id,
            "not in the plan; kept (--prune deletes a bot at rest)",
            desired_before=before,
            state=bot.state.value,
        )
    if permits_delete(bot.state):
        return PlanChange(
            ChangeAction.DELETE,
            *base[:2],
            bot.bot_id,
            "not in the plan; deleted (a rename is a delete and a create)",
            desired_before=before,
            state=bot.state.value,
        )
    return PlanChange(
        ChangeAction.BLOCKED,
        *base[:2],
        bot.bot_id,
        f"not in the plan but not deleted: needs stop first, the bot is {bot.state.value}",
        desired_before=before,
        state=bot.state.value,
    )


def _blocked(
    entry: PlannedBot,
    bot: BotSnapshot | None,
    detail: str,
    before: DesiredState | None = None,
) -> PlanChange:
    return PlanChange(
        ChangeAction.BLOCKED,
        entry.name,
        entry.venue,
        bot.bot_id if bot is not None else None,
        detail,
        planned=entry,
        desired_before=before,
        desired_after=entry.desired_state,
        state=bot.state.value if bot is not None else None,
    )


def _cannot_edit_in_place(entry: PlannedBot, bot: BotSnapshot) -> str:
    differing = [
        label
        for label, planned, stored in (
            ("kind", entry.kind, bot.kind),
            ("symbol", entry.symbol, bot.symbol),
        )
        if planned != stored
    ]
    if not differing:
        return ""
    return (
        f"{' and '.join(differing)} cannot be edited on a bot (its orders and lease are "
        "tied to them): that is a new bot - name it differently and use --prune"
    )


def _differing_params(
    planned: Mapping[str, str], stored: Mapping[str, str]
) -> list[str]:
    changes = [
        f"{key} {stored.get(key, '(unset)')} -> {planned.get(key, '(removed)')}"
        for key in sorted(set(planned) | set(stored))
        if planned.get(key) != stored.get(key)
    ]
    return changes


def _meaning(desired: DesiredState, state: BotLifecycleState) -> str:
    """What `desired_state` will mean for a bot in `state`, by the host's own rule.

    `run --start-planned` starts a bot that is at rest (`AT_REST_STATES`, the report's
    constant that the host asks), so a promise to start is made only for those; a bot
    that is HALTED, in ERROR, STARTING or STOPPING is not started, and the diff says so."""
    at_rest = state.value in AT_REST_STATES
    active = restarts_into_recovering(state)
    if desired is DesiredState.RUNNING:
        if at_rest:
            return "desired running: run --start-planned will start it"
        if active:
            return "desired running: already running, nothing to start"
        return (
            f"desired running: but the bot is {state.value}, so run --start-planned "
            "will not start it (only a bot at rest is started)"
        )
    if active:
        return f"desired stopped: apply does not stop a bot (it is {state.value})"
    return "desired stopped: run --start-planned leaves it"
