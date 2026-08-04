import os
import sys
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# Setup paths to ensure we can import from Binace_Bot
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from Binace_Bot.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.application.ports.i_market_data_repository import IMarketDataRepository
from sagittarius_engine.utils.path_utils import PathUtils

# Page config
st.set_page_config(page_title="Binance Trading Bot", layout="wide", page_icon="🤖")

# Cache the engine bootstrapping so it only happens once per session
@st.cache_resource
def get_market_data_repo():
    """Bootstraps the engine and returns the repository."""
    config_manager = ConfigManager()
    
    main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    app_json = PathUtils.get_relative_path(main_path, "config", "app_config.json")
    user_json = PathUtils.get_relative_path(main_path, "config", "user_config.json")
    
    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    
    app = create_app(config_manager)
    app.boot()
    return app.container.resolve(IMarketDataRepository)

repo = get_market_data_repo()

# UI Layout
st.title("🤖 Binance Bot Real-time Dashboard")

# Auto-refresh every 5 seconds
st_autorefresh(interval=5000, limit=None, key="market_data_refresh")

# Sidebar for controls
with st.sidebar:
    st.header("Controls")
    symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"], index=1)
    
    # We must match the TimeFrame enum string values
    timeframe_str = st.selectbox("Interval", ["1m", "3m", "5m", "15m", "1h", "4h", "1d"], index=0)
    interval = TimeFrame(timeframe_str)
    
    limit = st.slider("Candles Limit", min_value=50, max_value=500, value=100, step=50)

# Fetch data from repository
klines = repo.get_klines(
    symbol=symbol,
    interval=interval,
    limit=limit
)

if not klines:
    st.warning(f"No data available for {symbol} at {interval.value}. Start the stream bot to sync data!")
else:
    # Convert Domain Entities to a format suitable for Lightweight Charts
    # Lightweight Charts expects: time (string 'YYYY-MM-DD' or timestamp), open, high, low, close
    chart_data = []
    for k in klines:
        chart_data.append({
            # Using ISO string is safer for timezone issues (or use timestamp for speed)
            "time": k.open_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": k.open_price,
            "high": k.high_price,
            "low": k.low_price,
            "close": k.close_price,
        })
        
    chartOptions = {
        "layout": {
            "textColor": 'white',
            "background": {'type': 'solid', 'color': '#1E1E1E'}
        },
        "timeScale": {
            "timeVisible": True,
            "secondsVisible": False,
        }
    }
    
    seriesCandlestickChart = [{
        "type": 'Candlestick',
        "data": chart_data,
        "options": {
            "upColor": '#26a69a',
            "downColor": '#ef5350',
            "borderVisible": False,
            "wickUpColor": '#26a69a',
            "wickDownColor": '#ef5350'
        }
    }]
    
    st.subheader(f"{symbol} - {interval.value}")
    renderLightweightCharts([
        {
            "chart": chartOptions,
            "series": seriesCandlestickChart
        }
    ], 'candlestick')
    
    # Render raw data at the bottom for debugging/viewing
    df = pd.DataFrame([k.__dict__ for k in klines])
    with st.expander("Raw Data (Tail)"):
        st.dataframe(df.tail(10))
