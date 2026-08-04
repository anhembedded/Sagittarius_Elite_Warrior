from sagittarius_engine.base import BaseModule
from sagittarius_engine import App

from Binace_Bot.src.application.interfaces.i_market_data_repository import (
    IMarketDataRepository,
)
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.infrastructure.binance.client import PythonBinanceClient
from Binace_Bot.src.application.use_cases.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from Binace_Bot.src.application.use_cases.start_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamCommandHandler,
)
from Binace_Bot.src.application.use_cases.stop_live_stream import (
    StopLiveStreamCommand,
    StopLiveStreamCommandHandler,
)
from Binace_Bot.src.application.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Binace_Bot.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Binace_Bot.src.infrastructure.engine_adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Binace_Bot.src.application.use_cases.process_market_tick import (
    ProcessMarketTickCommand,
    ProcessMarketTickCommandHandler,
)
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.presentation.event_handlers.market_tick_reactor import (
    MarketTickReactor,
)
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


class BinanceBotModule(BaseModule):
    """
    Sagittarius Application Module for Binance Trading Bot.
    Registers repositories, use cases, and domain background services.
    """

    def __init__(self):
        pass

    def register(self, app: App) -> None:
        # Bind engine context dependencies for infrastructure services
        app.container.singleton(ITaskManager, app.context.tasks)

        # Register Repositories & Clients
        app.container.singleton(IMarketDataRepository, SQLAlchemyMarketDataRepository)
        app.container.singleton(IExchangeClient, PythonBinanceClient)

        # Bind UseCases (Command -> Handler)
        app.container.bind(SyncMarketDataCommand, SyncMarketDataCommandHandler)
        app.container.bind(StartLiveStreamCommand, StartLiveStreamCommandHandler)
        app.container.bind(StopLiveStreamCommand, StopLiveStreamCommandHandler)
        app.container.bind(ProcessMarketTickCommand, ProcessMarketTickCommandHandler)

        # Register the WebsocketService as bound to its Interface
        app.container.singleton(ILiveStreamService, BinanceWebsocketService)
        # Register the Adapter
        app.container.bind(LiveStreamEngineAdapter, LiveStreamEngineAdapter)

    def boot(self, app: App) -> None:
        # Register the adapter as a HostedService so it receives the EngineContext and is managed
        # by the App lifecycle, delegating to the pure ILiveStreamService.
        adapter = app.container.resolve(LiveStreamEngineAdapter)
        app.context.hosted_services.register(adapter)

        # Initialize Event Reactors and subscribe to the Event Bus
        reactor = MarketTickReactor(app)
        app.event_bus.on(MarketTickEvent, reactor.handle)
