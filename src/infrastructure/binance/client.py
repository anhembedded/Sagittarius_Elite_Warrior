from binance.client import Client
from datetime import datetime, timezone
from Binace_Bot.src.application.ports.i_exchange_client import IExchangeClient
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
import logging

logger = logging.getLogger("App.ExchangeClient")


class PythonBinanceClient(IExchangeClient):
    """
    @brief Infrastructure Adapter for python-binance.
    """

    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        # For public endpoints like klines, api_key/secret aren't strictly required,
        # but good to have for rate limits or private endpoints later.
        self.client = Client(api_key, api_secret)

    def get_historical_klines(
        self, symbol: str, interval: TimeFrame, start_str: str | datetime, end_str: str | datetime | None = None
    ) -> list[MarketData]:
        # Convert datetime to string or millisecond timestamp for python-binance if needed
        # python-binance accepts datetime, string ('1 day ago UTC'), or ms timestamp

        if isinstance(start_str, datetime):
            start_str = start_str.astimezone(timezone.utc).strftime("%d %b %Y %H:%M:%S")
            
        if isinstance(end_str, datetime):
            end_str = end_str.astimezone(timezone.utc).strftime("%d %b %Y %H:%M:%S")

        logger.info(
            f"Fetching historical klines for {symbol} at {interval.value} from {start_str} to {end_str or 'NOW'}"
        )
        try:
            raw_klines = []
            generator = self.client.get_historical_klines_generator(
                symbol, interval.value, start_str, end_str
            )
            for i, k in enumerate(generator):
                raw_klines.append(k)
                if (i + 1) % 10000 == 0:
                    logger.info(f"[{symbol}] Downloaded {i + 1} klines so far...")
            logger.debug(f"Successfully fetched {len(raw_klines)} klines for {symbol}.")
        except Exception as e:
            logger.error(f"Failed to fetch historical klines for {symbol}: {e}")
            raise

        market_data_list = []
        for k in raw_klines:
            market_data_list.append(
                MarketData(
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
                    taker_buy_quote_asset_volume=float(k[10]),
                )
            )

        return market_data_list
