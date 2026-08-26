# EPIC-010D — Dev Board: symbol, interval, and the lookback duration

**Status:** 🔵 Not started
**Repo:** **Elite** — design §8 step 3
**Depends on:** `EPIC-010B`

## What

`DashboardPresenter` implements the contributor contract, scope
`StateScope("dashboard", None, PERSISTENT)`:

| Value | Today | Persisted as |
| :--- | :--- | :--- |
| Symbol | `_DEFAULT_SYMBOL = "ETHUSDT"` hardcoded (`dashboard_view_model.py:26`) | `symbol` |
| Interval | `_DEFAULT_INTERVAL_STR = "1m"` (`dashboard_presenter.py:46`) | `interval` |
| Start/end date | recomputed `now - 7 days` per construction (`dashboard_view_model.py:77-79`) | **`lookback_days`** — see below |

## Dates are a duration, not timestamps 🟢 settled 2026-08-26

Design §9.1. Persist `{"lookback_days": 7}` and recompute `now - N days` on
restore. This **preserves today's behaviour exactly** rather than changing it,
and removes risk **R2**: a stale absolute window silently making Load History
fetch an enormous range after the app sits unused for a month.

## Restore is a request (D5) — validate each value separately

- Symbol: only apply if it is still in the symbol options the app knows about;
  otherwise fall back. A dropped symbol must **not** also discard the interval.
- Interval: only apply if still a valid `TimeFrame`.
- `lookback_days`: must be a positive int within a sane bound.

Validation lives **here**, not in the Engine — boundary rule 4: the framework
never decides whether a value is still valid.

## Restore must cause no side effects (mode #12)

`cboSymbol.currentTextChanged` is wired straight into a handler. Write the
**ViewModel**, not the widget. Where a widget genuinely must be touched, wrap it
in `QSignalBlocker` — measured to apply the value while emitting zero signals
(design §5.6.6 row 9).

> **Opening the app must not fetch anything.** The form is pre-filled; nothing
> runs until the user clicks. This is `BOT-062`'s decision, and D6 protects it.

## Acceptance

- Change symbol + interval, quit, relaunch → both come back, **and `dispatch`
  was never called during boot** (the integration test that proves mode #12)
- A persisted symbol no longer in the DB → falls back, interval still restored
- `lookback_days` absent or nonsense → today's `now - 7 days` behaviour
