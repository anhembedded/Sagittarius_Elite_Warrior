# SPEC-002 — Watch the live market for chosen symbols

- **Status:** ✅ built and proven
- **Actor:** trader
- **Origin:** measured from the code. `BOT-126` (one subscription set per owner, reference
  counted) and `BOT-033`/`BOT-034` (which symbol and timeframe a click actually uses) are the
  reports that shaped it.
- **Surfaces:** Dev Board's *Start Live* · the Trading screen's chart, which is live for as long
  as the screen is open · the Watchlist screen (`BOT-019`), live for as long as it is open,
  tracking several symbols under one `IMarketStream` owner rather than one chart's single symbol ·
  `stream start` / `stream stop` at the interactive prompt.

## 1. Trigger

*"I want this chart to keep moving on its own, not a snapshot I have to refresh."*

## 2. Preconditions

1. History for the symbol and timeframe is loaded, or is about to be: *Start Live* runs
   SPEC-001's fetch first and only then opens the websocket, so a live chart never starts from an
   empty canvas.
2. The timeframe is one of the sixteen `TimeFrame` values.
3. No API credentials are needed — the kline stream is public.

## 3. Main flow

1. The actor chooses a symbol and a timeframe, and starts the live view.
2. The app reads the symbol and timeframe **at click time**, not from whatever the picker shows
   later (`BOT-033`): a picker changed while the fetch is in flight does not silently redirect
   the stream.
3. The app brings history up to date (SPEC-001), showing that phase's progress.
4. The app subscribes to the live kline stream for those symbols under a named **stream owner** —
   `cli` for the prompt, its own name for each screen.
5. The app answers with two facts: whether the subscription set is now what the actor asked for,
   and a message when it is not.
6. Candles arrive and the chart updates in place: the forming candle is rewritten, a closed one
   is appended.
7. The actor stops the stream, or closes the screen, and the app releases **that owner's**
   subscription set.

## 4. What must be true afterwards

- While the stream is open, the chart's newest candle keeps changing without any further action
  from the actor.
- Starting a stream under the same owner **replaces** that owner's previous set. It does not add
  to it, and it does not touch another owner's streams: two screens may watch the same symbol,
  and one stopping leaves the other running (reference counted per symbol and timeframe,
  `BOT-126`).
- A stop that the actor asked for never leaves a socket open, and never publishes a candle
  afterwards into the screen that asked to stop.
- A failed start says so. The old shape of this call read `getattr(response, "success", True)`,
  which reported success for a stream that never opened; the port answers with a named type so
  there is nothing left to probe.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The websocket cannot be opened | `❌ Failed to start stream: …`, and the screen stays in its pre-live state | Step 5's answer carries `success=False` with the reason; the UI never shows "streaming" for a stream that is not |
| The socket drops mid-session | **Nothing** — the stream reconnects and the next candle arrives as usual | Measured, not assumed: the websocket service catches the transport error and re-opens the socket, so a transient drop is not an event the actor is told about |
| The actor clicks *Start Live* twice, or stops while a start is in flight | The later click wins; the earlier attempt's result is discarded rather than applied | Each click owns an action identity, and a result from a superseded action is fenced (`async-ui-action-rule.md`) |
| A bare `stream` is typed with no subcommand | A usage line | `argparse` yields `None` for an optional subcommand; answering with help beats a traceback |
| The symbol has no live market | The exchange's own refusal, reported as the start failure | The app keeps no local list of streamable pairs to pre-judge with |

## 6. What this use case does NOT promise

- **No per-stream handle.** An owner holds one subscription set, started and released together.
  A caller cannot stop one symbol out of three it asked for; it asks again with the two it
  wants. `SDD-06b` declares a `StreamHandle` shape, and `IMarketStream`'s own docstring records
  that it is not built — the seam is cut when `strategy` (Phase 2) needs one stream per armed
  symbol.
- A stream owner is a **namespace, not a lease**. Two owners streaming the same symbol is
  normal and is not a conflict; nothing here reserves a symbol against anybody.
- **It does not tell the actor that a drop happened.** A reconnect is silent, and the candles
  missed during the gap are not backfilled — running SPEC-001 again is what fills them. So a
  chart that reconnected can have a hole in it and still look continuous. That is the one
  place this use case is thinner than `domain-truth-rule.md` would like, and it is written
  here rather than discovered later.
- No order flow, no depth. This is klines only; the order book and the user-data stream are
  separate mechanisms.

## 7. Ports and modules it exercises

`market_data`: `IMarketStream` (start and stop for an owner, answering `StreamOutcome`),
`IMarketDataSync` (step 3), `IHistoricalKlines` (what the chart draws before the first live
candle arrives). `ILiveStreamService` is the module's own subscription bookkeeping and is not a
consumer-facing port.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Both implementations start, stop and answer alike | `tests/unit/modules/market_data/contracts/test_market_stream_contract.py` | contract |
| `stream start` / `stream stop`, including the bare-`stream` usage line | `tests/unit/modules/market_data/cli/test_stream_cmd.py` | unit |
| A stop or a second start cancels the in-flight one, and its result is fenced | `tests/unit/modules/trading/ui/dashboard/test_stream_lifecycle_cancellation.py` | unit |
| A transport error mid-stream reconnects, and the next candle still arrives | `tests/unit/modules/market_data/adapters/binance/test_binance_websocket_service.py` | unit |
| The stream's state reaches the actor as a status pill, every UI mode | `tests/unit/modules/trading/ui/dashboard/test_dev_board_panel.py` | unit |
| The Dev Board actually streams end to end | `tests/integration/modules/trading/ui/test_dashboard_live_stream.py` | integration |
| The Trading chart goes live on its own when the screen opens | `tests/unit/modules/trading/ui/trading/test_trading_presenter_chart_autostart.py` | unit |
| Live candles reach the chart and rewrite the forming one | `tests/unit/modules/trading/ui/trading/test_trading_presenter_chart_ticks.py` | unit |
| A real socket against the real venue | **the user runs it**: `stream start --symbols BTCUSDT --interval 1m`, watch the chart advance for a minute, then `stream stop` and see it settle | human |
