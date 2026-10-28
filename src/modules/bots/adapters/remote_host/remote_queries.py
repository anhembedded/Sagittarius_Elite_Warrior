"""`EPIC-047E` — the Bots screen's queries, answered from what the host published.

@details Each answer is a function of one `HostWorld`, so a test hands it a world and reads the value; no thread,
no link. The shapes are the ones the host's own handlers answer, and where a handler judged something from host
facts the judgement is the handler's own function (`venue_choices_of`, `plan_risk_of`, `host_run_facts`,
`occupancy_of`), called here with the facts the host published — not a second copy of the rule (P3).

@par A gap is a sentence
What the host never published is `NOT_PUBLISHED_BY_THE_HOST`, in the field the screen already shows a problem in
(`PlannerMarket.problem`, `BotFills.problem`, `ExchangeUnavailable.reason`), never a default that reads like a
fact (decision record 2026-10-27, D5).

@par Extension cases
  · another query the screen learns — one function here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_connection import (
    connection_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    export_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFills,
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_plan_risk_facts import (
    GetPlanRiskFactsQuery,
    plan_risk_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_choices import (
    GetVenueChoicesQuery,
    venue_choices_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    BotSlot,
    occupancy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    host_run_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    NOT_PUBLISHED_BY_THE_HOST,
    HostFile,
    HostFileState,
    HostWorld,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import BotRunFacts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_choice import (
    KEY_SAVED,
    NO_KEY,
    NOT_ENABLED,
    VenueChoices,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

UNKNOWN_BOT = "this bot is not in the host's list (it may have been deleted)"


class QueryNotServedError(LookupError):
    """The VPS tab serves no such query; the dispatcher says so in words."""

    def __init__(self, query: object) -> None:
        super().__init__(type(query).__name__)


class NotPublishedError(LookupError):
    """A read whose answer is a value the host never published (the budget caps, say): there is no honest
    default, so the read fails, the screen says it once, and Start keeps waiting for the facts."""


class RemoteQueries:
    """The queries the VPS tab serves; any other is `QueryNotServedError`."""

    def __init__(self, kinds: IBotKindCatalog) -> None:
        self._kinds = kinds

    def answer(self, query: object, world: HostWorld) -> object:
        gaps = _Gaps(
            _gap_words(world.held_file, "facts"), _gap_words(world.reads_file, "reads")
        )
        live = _live(world)
        match query:
            case ListBotsQuery():
                return _list(live)
            case GetBotFillsQuery():
                return _fills(query, live, gaps)
            case GetExchangeFactsQuery():
                return _snapshot(query.bot_id, live, gaps)
            case GetPlanRiskFactsQuery():
                return plan_risk_of(_snapshot(query.bot_id, live, gaps))
            case GetPlannerMarketQuery():
                return _planner(query, live, gaps)
            case GetBotRunFactsQuery():
                return _run_facts(query, live, gaps)
            case GetVenueConnectionQuery():
                return connection_of(
                    query.venue, query.symbol, live.bots, live.held, live.reads
                )
            case GetVenueChoicesQuery():
                return _choices(live, gaps, self._kinds)
            case ExportBotPlanQuery():
                return export_plan(live.bots, None, query.bot_ids)
            case _:
                raise QueryNotServedError(query)


@dataclass(frozen=True, slots=True)
class _Gaps:
    """The sentence for a published file that cannot be used: never published, or the host went quiet."""

    held: str
    reads: str


def _gap_words(file: HostFile, what: str) -> str:
    if file.state is not HostFileState.STALE:
        return NOT_PUBLISHED_BY_THE_HOST
    since = "" if file.age_s is None else f" for at least {int(file.age_s)} s"
    return (
        f"the host has not written its {what}{since}: it may have stopped, "
        "so its last picture is not shown as current"
    )


def _live(world: HostWorld) -> HostWorld:
    """`world` with a host file that is not live taken out: a `STALE` file is the last picture of a host that
    may have stopped, and an answer drawn from it would read as current (the bridge keeps the document)."""
    return replace(
        world,
        held=world.held if world.held_file.state is HostFileState.LIVE else None,
        reads=world.reads if world.reads_file.state is HostFileState.LIVE else None,
    )


def _list(world: HostWorld) -> BotList:
    return BotList(world.bots, world.refused)


def _bot(bot_id: str, world: HostWorld) -> BotSnapshot | None:
    return next((bot for bot in world.bots if bot.bot_id == bot_id), None)


def _snapshot(bot_id: str, world: HostWorld, gaps: _Gaps) -> VenueSnapshot:
    if _bot(bot_id, world) is None:
        return ExchangeUnavailable(UNKNOWN_BOT)
    held = world.held
    read = (
        None
        if held is None
        else next((r for r in held.exchange_reads if r.bot_id == bot_id), None)
    )
    return ExchangeUnavailable(gaps.held) if read is None else read.snapshot


def _fills(query: GetBotFillsQuery, world: HostWorld, gaps: _Gaps) -> BotFills:
    if _bot(query.bot_id, world) is None:
        return BotFills(problem=UNKNOWN_BOT)
    reads = world.reads
    read = (
        None
        if reads is None
        else next((r for r in reads.fills if r.bot_id == query.bot_id), None)
    )
    return BotFills(problem=gaps.reads) if read is None else read.fills


def _planner(
    query: GetPlannerMarketQuery, world: HostWorld, gaps: _Gaps
) -> PlannerMarket:
    reads = world.reads
    on_market = {
        bot.bot_id
        for bot in world.bots
        if bot.venue is query.venue and bot.symbol == query.symbol
    }
    read = None
    if reads is not None:
        candidates = [r for r in reads.planner if r.bot_id in on_market]
        read = max(candidates, key=lambda r: r.read_at, default=None)
    if read is None:
        return PlannerMarket(None, None, None, None, gaps.reads)
    return read.market


def _run_facts(
    query: GetBotRunFactsQuery, world: HostWorld, gaps: _Gaps
) -> BotRunFacts:
    held = world.held
    occupancy = occupancy_of(
        query.bot_id,
        query.venue,
        query.symbol,
        (BotSlot(b.bot_id, b.venue, b.symbol, b.state) for b in world.bots),
        (refused.name for refused in world.refused),
    )
    if held is None:
        raise NotPublishedError(gaps.held)
    lease = next(
        (
            lease.holder
            for lease in held.leases
            if lease.venue is query.venue and lease.symbol == query.symbol
        ),
        "",
    )
    return host_run_facts(
        query.bot_id, query.venue, held.enabled_venues, lease, occupancy, held.caps
    )


def _choices(world: HostWorld, gaps: _Gaps, kinds: IBotKindCatalog) -> VenueChoices:
    held = world.held

    def connection(venue: TradingVenue) -> str:
        if held is None:
            return gaps.held
        if venue not in held.enabled_venues:
            return NOT_ENABLED
        saved = any(k.venue is venue and k.key_saved for k in held.venue_keys)
        return KEY_SAVED if saved else NO_KEY

    return venue_choices_of(kinds, connection)
