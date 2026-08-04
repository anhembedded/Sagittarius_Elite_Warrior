import os
import sys
import time
import pandas as pd
from datetime import datetime
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from Binace_Bot.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.application.use_cases.run_backtest import RunBacktestCommand
from sagittarius_engine.utils.path_utils import PathUtils
from lightweight_charts import Chart

def boot_engine():
    config_manager = ConfigManager()
    main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    app_json = PathUtils.get_relative_path(main_path, "config", "app_config.json")
    user_json = PathUtils.get_relative_path(main_path, "config", "user_config.json")
    
    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    
    app = create_app(config_manager)
    app.boot()
    return app

def main():
    app = boot_engine()
    
    # Configure Backtest Parameters
    symbol = "BTCUSDT"
    interval = TimeFrame.ONE_MINUTE
    limit = 500
    replay_speed_ms = 50 # Speed up for simulation
    
    # Initialize the Chart
    chart = Chart(inner_width=1.0, inner_height=1.0)
    chart.time_scale(right_offset=50, min_bar_spacing=2)
    chart.layout(background_color='#1E1E1E', text_color='#FFFFFF')
    chart.watermark(symbol, color='rgba(255, 255, 255, 0.1)')

    is_initialized = [False]

    # We need to map MarketTickEvent to the chart
    def on_market_tick(event: MarketTickEvent):
        if event.market_data.symbol == symbol:
            # lightweight_charts expects a dict or a pandas Series
            # with time, open, high, low, close, volume
            data = {
                "time": event.market_data.open_time.strftime("%Y-%m-%d %H:%M:%S"),
                "open": event.market_data.open_price,
                "high": event.market_data.high_price,
                "low": event.market_data.low_price,
                "close": event.market_data.close_price,
                "volume": event.market_data.volume
            }
            if not is_initialized[0]:
                chart.set(pd.DataFrame([data]))
                is_initialized[0] = True
            else:
                chart.update(pd.Series(data))
    
    # Subscribe to Event Bus
    app.event_bus.on(MarketTickEvent, on_market_tick)
    
    def run_simulation():
        # Give the chart a moment to render before blasting events
        time.sleep(2) 
        
        command = RunBacktestCommand(
            symbol=symbol,
            interval=interval,
            limit=limit,
            replay_speed_ms=replay_speed_ms
        )
        # Resolve the handler and execute
        # We bypass CQRS dispatcher for direct execution in this simple entrypoint
        from Binace_Bot.src.application.use_cases.run_backtest import RunBacktestCommandHandler
        handler = app.container.resolve(RunBacktestCommandHandler)
        handler.execute(command)
        
        print("Simulation Thread Finished.")
    
    # Run simulation in a background thread so it doesn't block the UI
    sim_thread = threading.Thread(target=run_simulation, daemon=True)
    sim_thread.start()
    
    print("Starting Desktop Chart UI...")
    # This will block the main thread and open the window
    chart.show(block=True)
    
    print("Chart closed. Shutting down engine...")
    app.stop()

if __name__ == "__main__":
    main()
