from pydantic import BaseModel
from Binace_Bot.src.domain.entities.market_data import MarketData

class ProcessMarketTickCommand(BaseModel):
    """
    @brief Command triggered when a new market tick is received.
    """
    market_data: MarketData
    model_config = {"arbitrary_types_allowed": True}
