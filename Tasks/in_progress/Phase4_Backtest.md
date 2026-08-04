# Phase 4: Backtesting Engine (Desktop UI)

## Goal
Build a local Desktop Application to backtest trading strategies against historical market data (stored in SQLite). The application will simulate a real-time feed by reading past data and pushing it into the engine using the same `MarketTickEvent` as the live system, ensuring 100% logic parity.

## Core Requirements
1. **Desktop UI**: Use the `lightweight_charts` Python library to spawn a standalone Window for visualizing the backtest.
2. **Historical Data Source**: Query candles (klines) from the local SQLite database via `IMarketDataRepository`.
3. **Simulation Loop**: A loop that reads data sequentially and pushes updates to the chart.
4. **Logic Parity**: Ensure the system uses the existing CQRS and Event-Driven architecture (e.g., `MarketTickEvent`) without introducing Backtrader or other monolithic frameworks.

## Tasks
- [ ] Research `lightweight_charts` API for Python to set up a basic standalone window.
- [ ] Create `src/presentation/ui/backtest_app.py` as the entry point for the backtester.
- [ ] Implement the `BacktestSimulator` loop to query SQLite and dispatch `MarketTickEvent`s.
- [ ] Bind the `MarketTickReactor` to update the desktop UI chart live as the simulator runs.
