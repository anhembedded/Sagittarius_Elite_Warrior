"""`EPIC-038D` - the host's "resume the RECOVERING bots": each bot's own Resume, asked for all of them.

A restart leaves RUNNING and PAUSED bots RECOVERING until a person resumes them (ADR 038 O2). The
screen's way is the bot's `ResumeBotCommand`: it opens the venue's order session for that bot and its
executor reconciles it with the exchange (`BUG-204`). This handler sends that same command for every
RECOVERING bot of the venue, so the reconciliation a headless resume runs is the one the GUI runs,
and it does not depend on a session-opening event: a session that is already open (a halted bot's
resume opened it a moment ago) publishes none, and an opening names the bot it was for (`BOT-183`),
so no other bot would be woken by it. It reports per venue because the session is the venue's.

Real money (decision O8): a mainnet venue is resumed only when the operator typed its name
(`--confirm-venue`); otherwise it is skipped, said so, and its bots stay RECOVERING.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
    VenueResumeOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class ResumeRecoveringForHostCommandHandler(
    ICommandHandler[ResumeRecoveringForHostCommand, ResumeRecoveringResult]
):
    def __init__(self, store: IBotStore, dispatcher: ICommandDispatcher) -> None:
        self._store = store
        self._dispatcher = dispatcher

    def execute(
        self, command: ResumeRecoveringForHostCommand
    ) -> ResumeRecoveringResult:
        return ResumeRecoveringResult(
            tuple(
                self._resume(venue, bot_ids, command.confirmed_venue)
                for venue, bot_ids in self._recovering_by_venue().items()
            )
        )

    def _recovering_by_venue(self) -> Mapping[TradingVenue, tuple[str, ...]]:
        grouped: dict[TradingVenue, list[str]] = {}
        for stored in self._store.load_all().bots:
            if stored.bot.state is BotLifecycleState.RECOVERING:
                grouped.setdefault(stored.bot.definition.venue, []).append(
                    stored.bot.bot_id.value
                )
        return {venue: tuple(ids) for venue, ids in grouped.items()}

    def _resume(
        self, venue: TradingVenue, bot_ids: tuple[str, ...], confirmed: str | None
    ) -> VenueResumeOutcome:
        if venue.is_mainnet and confirmed != venue.value:
            return VenueResumeOutcome(
                venue.value,
                bot_ids,
                opened=False,
                note=f"{venue.display_name} trades real money: resuming needs --confirm-venue "
                f"{venue.value}; {', '.join(bot_ids)} stay RECOVERING",
            )
        not_resumed: list[str] = []
        for bot_id in bot_ids:
            resumed = cast(
                BotCommandResult,
                self._dispatcher.dispatch(
                    ResumeBotCommand,
                    ResumeBotCommand(bot_id, real_money_confirmed=venue.is_mainnet),
                ),
            )
            if not resumed.accepted:
                not_resumed.append(f"{bot_id} stays RECOVERING ({resumed.message})")
        if not_resumed:
            return VenueResumeOutcome(
                venue.value, bot_ids, opened=False, note="; ".join(not_resumed)
            )
        return VenueResumeOutcome(venue.value, bot_ids, opened=True)
