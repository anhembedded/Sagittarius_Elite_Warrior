from sagittarius_engine.interfaces import IEngineContext, IExtension
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.application.interfaces.i_market_data_repository import IMarketDataRepository
from Binace_Bot.src.infrastructure.binance.client import PythonBinanceClient
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import SQLAlchemyMarketDataRepository
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.sync_market_data_handler import SyncMarketDataCommandHandler

class DataSyncExtension(IExtension):
    """
    @brief Initializes DI mappings for Data Sync Phase 1.
    """
    
    def register(self, context: IEngineContext) -> None:
        # Register Infrastructure adapters
        context.container.singleton(IExchangeClient, PythonBinanceClient)
        context.container.singleton(IMarketDataRepository, SQLAlchemyMarketDataRepository)
        
        # Register Command Handler manually for this specific command.
        # In a full CQRS setup, this would be auto-discovered.
        # We can register the handler instance directly or resolve dependencies.
        def _build_handler(ctx):
            exchange = ctx.resolve(IExchangeClient)
            repo = ctx.resolve(IMarketDataRepository)
            return SyncMarketDataCommandHandler(exchange, repo, context.logger)
            
        context.container.singleton(SyncMarketDataCommandHandler, _build_handler)

    def boot(self, context: IEngineContext) -> None:
        pass

    def shutdown(self, context: IEngineContext) -> None:
        pass
