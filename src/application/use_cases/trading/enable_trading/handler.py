import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading.command import (
    EnableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading.result import (
    EnableTradingBlockReason,
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
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

    Builds its own `FuturesTradingClient` (`VALIDATE_ONLY` — irrelevant
    for these two read-only calls) from the same raw collaborators
    `ExecuteOrderCommandHandler` uses, rather than depending on the
    `ITradingClient` singleton directly: that singleton is only
    registered when `TradingVenue != DISABLED`
    (`binance_bot_module.py`), and this handler must still be
    *constructible* (to report `TRADING_VENUE_DISABLED` itself) when it
    is not.

    Starts `IUserDataStream` on a successful enable (`EPIC-021H` §3) —
    the exchange's own account of what happens to an order only starts
    flowing once trading is actually turned on, never merely because the
    app booted.
    """

    def __init__(
        self,
        trading_venue: TradingVenue,
        account_reader: ITradingAccountReader,
        session_factory: ExchangeSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
        session_state: TradingSessionState,
        user_data_stream: IUserDataStream,
    ) -> None:
        self._trading_venue = trading_venue
        self._account_reader = account_reader
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider
        self._session_state = session_state
        self._user_data_stream = user_data_stream

    def execute(self, command: EnableTradingCommand) -> EnableTradingResult:
        logger.debug("Handling EnableTradingCommand")

        if self._trading_venue is not TradingVenue.FUTURES_TESTNET:
            return self._blocked(EnableTradingBlockReason.TRADING_VENUE_DISABLED)

        status = self._account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return self._blocked(EnableTradingBlockReason.CONNECTION_NOT_READY)

        trading_client = FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            OrderSubmissionMode.VALIDATE_ONLY,
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

        self._session_state.enable({position.symbol for position in positions})
        self._user_data_stream.start()
        logger.info(
            "Trading enabled for this session (%d open orders reconciled).",
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
