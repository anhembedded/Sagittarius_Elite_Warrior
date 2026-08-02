from binance.client import Client
from datetime import datetime, timezone
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class PythonBinanceClient(IExchangeClient):
    """
    @brief Infrastructure Adapter for python-binance.
    """
    
    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        # For public endpoints like klines, api_key/secret aren't strictly required, 
        # but good to have for rate limits or private endpoints later.
        self.client = Client(api_key, api_secret)
        
    def get_historical_klines(self, symbol: str, interval: TimeFrame, start_str: str | datetime) -> list[MarketData]:
        # Convert datetime to string or millisecond timestamp for python-binance if needed
        # python-binance accepts datetime, string ('1 day ago UTC'), or ms timestamp
        
        if isinstance(start_str, datetime):
            # Convert to UTC string if it's a datetime
            start_str = start_str.astimezone(timezone.utc).strftime("%d %b %Y %H:%M:%S")
            
        raw_klines = self.client.get_historical_klines(symbol, interval.value, start_str)
        
        market_data_list = []
        for k in raw_klines:
            market_data_list.append(MarketData(
                symbol=symbol,
                interval=interval.value,
                open_time=datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc),
                open_price=float(k[1]),
                high_price=float(k[2]),
                low_price=float(k[3]),
                close_price=float(k[4]),
                volume=float(k[5]),
                close_time=datetime.fromtimestamp(k[6] / 1000.0, tz=timezone.utc),
                quote_asset_volume=float(k[7]),
                number_of_trades=int(k[8]),
                taker_buy_base_asset_volume=float(k[9]),
                taker_buy_quote_asset_volume=float(k[10])
            ))
            
        return market_data_list
