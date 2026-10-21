"""`EPIC-045A` - the host's "create this bot", answered by the screen's own New bot.

The owner designs a bot in the desktop app, exports the plan and wants it on the VPS without
stopping the host (a restart sends every RUNNING bot through RECOVERING and a manual resume).
`bot apply` needs the data root's writable lock, which the host holds; this handler is the create
reached through the command directory. It adds no way to create a bot: it dispatches the very
`CreateBotCommand` the Bots tab and `bot apply` dispatch, so the bot lands DRAFT, as every created
bot does (P5).

Order, so that a refusal creates nothing and says why:
  1. the venue is one this build trades on;
  2. the kind exists, and no parameter is named like a credential (a plan refuses them too);
  3. the kind judges the parameters without the exchange (`IBotKind.parameter_problem`: an unknown
     key or an unreadable value is refused in words);
  4. no bot already has this name on this venue (the identity a plan uses; `bot edit` changes it);
  5. the bot is created, and the reply names its id.

An add places no order and needs no `--confirm-venue`, on a mainnet venue too: the money question
stays at `bot start`, whose guard is untouched. It records no desired state, so
`run --start-planned` does not start it.

@par Concurrency
Steps 1-5 run under `BotCommandLock`, the lock a Start and an Edit hold, so a start cannot read the
bots half way through an add and two adds of the same name cannot both pass step 4.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    is_secret_name,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AddBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class AddBotForHostCommandHandler(
    ICommandHandler[AddBotForHostCommand, BotCommandResult]
):
    def __init__(
        self,
        store: IBotStore,
        dispatcher: ICommandDispatcher,
        kinds: IBotKindCatalog,
        lock: BotCommandLock,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._kinds = kinds
        self._lock = lock

    def execute(self, command: AddBotForHostCommand) -> BotCommandResult:
        entry = command.entry
        with self._lock.held():
            venue = _venue_of(entry)
            if not isinstance(venue, TradingVenue):
                return _refused(venue)
            problem = self._kind_problem(entry) or _secret_problem(entry)
            if problem:
                return _refused(problem)
            problem = self._duplicate_problem(entry, venue)
            if problem:
                return _refused(problem)
            created = cast(
                BotCommandResult,
                self._dispatcher.dispatch(
                    CreateBotCommand,
                    CreateBotCommand(
                        entry.name,
                        entry.kind,
                        venue,
                        entry.symbol,
                        {setting.key: setting.value for setting in entry.params},
                    ),
                ),
            )
            if not created.accepted:
                return BotCommandResult.refused(
                    created.refusal or BotRefusal.INVALID_DEFINITION,
                    f"{created.message} Nothing was created.",
                )
            return BotCommandResult(
                accepted=True,
                bot_id=created.bot_id,
                message=_accepted_words(created.bot_id or "", entry),
            )

    def _kind_problem(self, entry: NewBotEntry) -> str:
        try:
            kind = self._kinds.kind(entry.kind)
        except UnknownBotKindError:
            return f"this build has no kind of bot {entry.kind!r}"
        config = {setting.key: setting.value for setting in entry.params}
        return kind.parameter_problem(config, list(config)) or ""

    def _duplicate_problem(self, entry: NewBotEntry, venue: TradingVenue) -> str:
        for stored in self._store.load_all().bots:
            held = stored.bot.definition
            if held.name == entry.name and held.venue is venue:
                return (
                    f"bot {stored.bot.bot_id.value} already has the name {entry.name!r} on "
                    f"{venue.value}; change its parameters with `bot edit {stored.bot.bot_id.value}` "
                    "or choose another name"
                )
        return ""


def _venue_of(entry: NewBotEntry) -> TradingVenue | str:
    for venue in TradingVenue:
        if venue is not TradingVenue.DISABLED and venue.value == entry.venue:
            return venue
    allowed = ", ".join(v.value for v in TradingVenue if v is not TradingVenue.DISABLED)
    return f"{entry.venue!r} is not a venue of this build; one of: {allowed}"


def _secret_problem(entry: NewBotEntry) -> str:
    named = [s.key for s in entry.params if is_secret_name(s.key)]
    if named:
        return (
            f"{', '.join(named)} is named like a secret and is refused; "
            "a bot holds no key, secret or account identifier"
        )
    return ""


def _refused(words: str) -> BotCommandResult:
    return BotCommandResult.refused(
        BotRefusal.INVALID_DEFINITION, f"{words}. Nothing was created."
    )


def _accepted_words(bot_id: str, entry: NewBotEntry) -> str:
    return (
        f"bot {bot_id} was created: {entry.name} ({entry.kind}) on {entry.venue}, {entry.symbol}. "
        f"It is DRAFT and starts only when you `bot start {bot_id}`"
        f"{' --confirm-venue ' + entry.venue if entry.venue.endswith('mainnet') else ''}; "
        "it is not in state/bot_plan.json, so `run --start-planned` does not start it"
    )
