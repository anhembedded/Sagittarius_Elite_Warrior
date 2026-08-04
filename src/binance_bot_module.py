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
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.sync_market_data_handler import (
    SyncMarketDataCommandHandler,
)
from Binace_Bot.src.application.use_cases.manage_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamCommandHandler,
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

        # Register the WebsocketService as bound to its Interface
        app.container.singleton(ILiveStreamService, BinanceWebsocketService)
        # Register the Adapter
        app.container.bind(LiveStreamEngineAdapter, LiveStreamEngineAdapter)

    def boot(self, app: App) -> None:
        # Register the adapter as a HostedService so it receives the EngineContext and is managed
        # by the App lifecycle, delegating to the pure ILiveStreamService.
        adapter = app.container.resolve(LiveStreamEngineAdapter)
        app.context.hosted_services.register(adapter)
