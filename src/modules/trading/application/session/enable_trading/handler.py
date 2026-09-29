import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.enable_trading.command import (
    EnableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

logger = logging.getLogger("App.CommandHandler")


class EnableTradingCommandHandler(
    ICommandHandler[EnableTradingCommand, EnableTradingResult]
):
    """
    @brief Handler for `EnableTradingCommand` — the one place
    `TradingSessionState.enable()` is ever called (`EPIC-021G` §2.4).

    @details Reconciles against the exchange every time, never trusts a
    previous session's state: `get_positions()`/`get_open_orders()` with
    no symbol read the *whole* account. Any existing position refuses the
    enable outright — this app never auto-adopts or auto-closes a
    position it did not open itself.

    `EPIC-028B` — acts on `command.venue` only. A venue that cannot submit
    orders is refused as `TRADING_VENUE_DISABLED` before anything is
    resolved; otherwise one `VenueTradingScopes.get()` call supplies that
    venue's client factory (`VALIDATE_ONLY` — irrelevant for these two
    read-only calls), account reader, session state and user data stream.

    Starts `IUserDataStream` on a successful enable (`EPIC-021H` §3) —
    the exchange's own account of what happens to an order only starts
    flowing once trading is actually turned on, never merely because the
    app booted.

    `BUG-112` — no longer requires an armed strategy (`EPIC-022B`'s
    original rule): that rule assumed "trading enabled" only ever meant
    "the automated strategy may act", which stopped being true once
    `EPIC-024B` gave `ExecuteOrderCommand` a second, independent caller —
    a human, via the manual order card. Requiring an armed strategy just
    to unlock manual-only trading forced a user into arming one on some
    symbol, which then immediately hard-blocked manual trading on that
    exact symbol (`PRO-003` §4.1.2) — a real deadlock, reported directly.

    `EPIC-027M` — on a Spot venue, `positions` is always empty
    (`SpotTradingClient.get_positions()`'s own docstring), so the
    `UNEXPECTED_POSITIONS` refusal above never actually fires for Spot —
    holding assets is normal there and says nothing about whether this app
    opened them. What Spot needs instead is recorded here: the account's
    current per-asset holdings (`status.holdings`, already fetched by the
    connection check above — no second network call) become the session's
    baseline, so `EmergencyStopCommandHandler` later knows exactly how much
    of each asset this app itself is responsible for, never the balance the
    user already held before enabling.
    """

    def __init__(self, scopes: VenueTradingScopes) -> None:
        self._scopes = scopes

    def execute(self, command: EnableTradingCommand) -> EnableTradingResult:
        logger.debug("Handling EnableTradingCommand on %s", command.venue.value)

        if not command.venue.supports_order_submission:
            return self._blocked(EnableTradingBlockReason.TRADING_VENUE_DISABLED)
        # `EPIC-028B` — everything below is `command.venue`'s own: its state,
        # connection, client and user data stream. Enabling one venue never
        # touches the other's session.
        scope = self._scopes.get(command.venue)
        session_state = scope.session_state

        # `BUG-088` — read *before* the two network round-trips below, not
        # after: `enable()` only applies if nothing else (a concurrent
        # Emergency Stop, most importantly) mutated `_session_state` while
        # this reconciliation was in flight.
        generation_before_reconciliation = session_state.generation

        status = scope.ports.account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return self._blocked(EnableTradingBlockReason.CONNECTION_NOT_READY)

        trading_client = scope.ports.client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        positions = tuple(trading_client.get_positions())
        open_orders = tuple(trading_client.get_open_orders())
        if positions:
            return EnableTradingResult(
                enabled=False,
                block_reason=EnableTradingBlockReason.UNEXPECTED_POSITIONS,
                reconciled_positions=positions,
                reconciled_open_orders=open_orders,
            )

        # `positions` is provably empty here (the `if positions:` branch
        # above already returned otherwise) — `set()`, not
        # `{p.symbol for p in positions}`, which read as if it seeded from
        # real data while always producing the same empty set.
        spot_baseline_holdings = (
            {holding.asset: holding.total for holding in status.holdings}
            if command.venue.market_type is MarketType.SPOT
            and status.holdings is not None
            else None
        )
        applied = session_state.enable(
            set(),
            expected_generation=generation_before_reconciliation,
            spot_baseline_holdings=spot_baseline_holdings,
        )
        if not applied:
            logger.warning(
                "EnableTradingCommand superseded — session state changed "
                "while reconciling (e.g. a concurrent Emergency Stop). "
                "Not enabling trading."
            )
            return EnableTradingResult(
                enabled=False,
                block_reason=(
                    EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE
                ),
                reconciled_positions=positions,
                reconciled_open_orders=open_orders,
            )

        scope.ports.user_data_stream.start()
        if spot_baseline_holdings is not None:
            logger.info(
                "Spot holdings baseline recorded for this session: %d asset(s).",
                len(spot_baseline_holdings),
            )
        logger.info(
            "Trading enabled on %s for this session (%d open orders reconciled).",
            command.venue.value,
            len(open_orders),
        )
        return EnableTradingResult(
            enabled=True,
            block_reason=None,
            reconciled_positions=positions,
            reconciled_open_orders=open_orders,
        )

    @staticmethod
    def _blocked(reason: EnableTradingBlockReason) -> EnableTradingResult:
        return EnableTradingResult(
            enabled=False,
            block_reason=reason,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
