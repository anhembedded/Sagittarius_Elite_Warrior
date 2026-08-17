# Backtest lifecycle — current workload context

> This is context, not a replacement for `.agents/rules/code-rule.md`.
> Update it when BOT-095 status or the relevant architecture changes.

## Current state

- `BOT-095A` is implemented in the shared Engine:
  `DeclarativeStateMachine` is event-driven and loaded by
  `BasePresenter.UI_TRANSITION_MATRIX`.
- `BOT-095B` is implemented in the Backtest screen:
  `logic/backtest_fsm_matrix.py` owns `BacktestUiState`,
  `BacktestUiEvent`, transition matrix, disabled modes and
  `BacktestRunConfig`. Dirty tracking dims stale results and exposes a
  config diff summary.
- `RunStaticBacktestCommandHandler` is synchronous today. It loads candles,
  simulates the full run and then runs in/out-of-sample validation. It has no
  cancellation/progress contract yet.
- `BackTestPresenter` submits work to `IThreadManager` and returns through
  Qt signals. It currently auto-runs after sync success and only logs
  reference-indicator selection changes.

## Required delivery order

1. `BOT-095H` — action ownership and stale-callback fencing.
2. `BOT-095C` — cancellation, progress and ETA for every simulation pass.
3. `BOT-095D` — UTC/cadence-aware coverage probe, sync progress and guarded
   auto-sync/run.
4. `BOT-095E` and `BOT-095F` — validation/stepper and async-safe indicator
   rendering.
5. `BOT-095G` — immutable, provenance-rich session history.

## Semantics that must not drift

- “No historical candles” is distinct from a completed backtest with zero
  trades. The latter still has valid metrics.
- A successful sync is only permission to continue the *same* active run
  intent after a post-sync coverage check; it is not permission to infer a
  new intent from live toolbar values.
- Reference indicators are visualization-only. Their toggle must not rerun
  the strategy or dirty the execution configuration.
- A restored history snapshot must hydrate UI atomically without triggering
  config-dirty tracking, then show the provenance of that historical result.

## Relevant evidence

- `Tasks/reports/BOT-095_review_phan_bien.md` — rationale and critique.
- `Tasks/backlog/BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md`
  — prerequisite contract for async work.
- `Tasks/backlog/BOT-095_backtest_signals_fsm_lifecycle_epic.md` — task board
  and acceptance criteria.
