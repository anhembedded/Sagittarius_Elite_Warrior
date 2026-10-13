"""`EPIC-038D` - the host's "resume the RECOVERING bots", answered by the screen's own session open.

The Bots tab never resumes a RECOVERING bot itself: the first deliberate action that
trades opens the venue's order session (`ITradingSession.ensure_ready`, SPEC-004), the
session announces itself on the bus, and the router tells every bot on that venue to
reconcile with the exchange. This handler is that open and nothing more, so the
reconciliation a headless resume runs is the one the GUI runs. It asks per venue, not
per bot, because the session is the venue's.

Real money (decision O8): a mainnet venue is opened only when the operator typed its
name (`--confirm-venue`); otherwise it is skipped, said so, and its bots stay RECOVERING.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.order_session_opening import (
    order_session_refusal_words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
    VenueResumeOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    bot_closed_reason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class ResumeRecoveringForHostCommandHandler(
    ICommandHandler[ResumeRecoveringForHostCommand, ResumeRecoveringResult]
):
    def __init__(self, store: IBotStore, ports: IVenueTradingPorts) -> None:
        self._store = store
        self._ports = ports

    def execute(
        self, command: ResumeRecoveringForHostCommand
    ) -> ResumeRecoveringResult:
        return ResumeRecoveringResult(
            tuple(
                self._open(venue, bot_ids, command.confirmed_venue)
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

    def _open(
        self, venue: TradingVenue, bot_ids: tuple[str, ...], confirmed: str | None
    ) -> VenueResumeOutcome:
        closed = bot_closed_reason(venue)
        if closed is not None:
            return VenueResumeOutcome(venue.value, bot_ids, opened=False, note=closed)
        if venue.is_mainnet and confirmed != venue.value:
            return VenueResumeOutcome(
                venue.value,
                bot_ids,
                opened=False,
                note=f"{venue.display_name} trades real money: resuming needs --confirm-venue {venue.value}",
            )
        refusal = order_session_refusal_words(
            self._ports.get(venue).trading_session, f"Venue {venue.value}"
        )
        if refusal is None:
            return VenueResumeOutcome(venue.value, bot_ids, opened=True)
        return VenueResumeOutcome(
            venue.value,
            bot_ids,
            opened=False,
            note=f"the order session did not open: {refusal}",
        )
