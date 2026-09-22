"""`BOT-025` — the Backtest module's domain event catalog, and why it stops
at two events.

@par The catalog
Exactly two events exist, one file each, both plain dataclasses inheriting
`sagittarius_engine`'s `BaseEvent`:

- `BacktestCompletedEvent` (`backtest_completed_event.py`) — carries the
  final `BacktestResult`.
- `BacktestFailedEvent` (`backtest_failed_event.py`) — carries a `reason`
  string; today only ever raised for "no historical data for this
  symbol/timeframe/range" (see both handlers' `execute()`), never for an
  unhandled exception, which propagates uncaught instead.

Both `RunStaticBacktestCommandHandler` (`application/run_static_backtest/`)
and `RunHistoricalTickBacktestCommandHandler`
(`application/run_historical_tick_backtest/`) publish exactly this pair,
once each, at the very end of `execute()` — Completed on a real result
(0 trades included), Failed on the one no-data path. Neither handler
publishes anything else; `tests/unit/modules/backtesting/contracts/events/
test_events_catalog.py` locks the file list so a third event added here
without updating this docstring fails loudly.

@par Who listens
Today, only `BackTestPresenter` (`_handle_backtest_completed_event`/
`_handle_backtest_failed_event`, wired in `signal_wiring.py`'s
`connect_engine_events`) — and only to write one dev-mode UI log line. This
is a secondary echo, not the primary update path: the Presenter already
gets the same outcome synchronously as `execute()`'s own return value,
routed through its own Qt signals
(`_backtestSucceededSignal`/`_backtestFailedSignal`). Both
`RunHistoricalTickBacktestCommandHandler`'s and
`RunStaticBacktestCommandHandler`'s own docstrings already note this split:
the event publisher is "a separate concern from the engine's signals".

`BOT-018` (Notifications/Alerting) would be a second, real consumer —
subscribing here to relay a long Realtime run's outcome over Telegram — but
that task is still in the backlog, so no such subscription exists yet.

@par What this catalog deliberately does NOT have, and why
The task that used to govern this module (`BOT-025`, filed against `BOT-023`
"Dynamic" backtest before that mode was cancelled) assumed six events that
were never built: `BacktestRunRequestedEvent`, `BacktestProgressEvent`,
`BacktestTradeSimulatedEvent`, `BacktestStoppedEvent`, `BacktestPausedEvent`,
`BacktestResumedEvent`, in a `domain/events/backtest_events.py` module that
never existed either (this package, `contracts/events/`, has always been
the real location — one file per event, the same convention every other
`contracts/` dataclass in this module follows). None of the six is a gap:

- **Progress** — both handlers report progress through a plain
  `progress_callback` (`ProgressThrottle`, `application/progress_throttle.py`)
  straight to the Presenter, never through `IEventPublisher`. Progress fires
  at tick/bar frequency; publishing that as a domain event would flood the
  bus for a UI-local concern with no other bounded-context consumer —
  exactly the kind of event Completed/Failed are not.
- **TradeSimulated** — never implemented; every closed trade is returned in
  the final `BacktestResult.trades` list, not streamed one event per trade
  as it closes. Same frequency argument as Progress.
- **Stopped** (cancellation) — represented by `BacktestCancelled`
  (`contracts/backtest_cancelled.py`), a plain return-value marker from
  `execute()`, not a domain event. Cancellation is a UI-driven interrupt
  local to one run; no other bounded context needs to react to it.
- **Paused/Resumed** — no pause/resume feature exists anywhere in this
  codebase (grepped `src/`: nothing). Both were speculative for "Dynamic",
  cancelled before it was ever built (see `BOT-023`'s own cancellation
  record). Neither surviving mode (Static, Realtime) pauses: each either
  runs to completion or fails.

Adding any of the six back is a real, currently-unclaimed enhancement, not
a gap this catalog left unfinished. The one action item from the original
`BOT-025` task that is still real — wiring `BacktestCompletedEvent`/
`BacktestFailedEvent` into `BOT-018` (Notifications) once that task exists —
stays deferred: `BOT-018` is still in the backlog, unbuilt, so there is
nothing to wire into yet.
"""
