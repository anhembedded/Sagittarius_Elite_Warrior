# CS-009 — The pace the journeys never ran

`BUG-194`, `BUG-238`, `BUG-241` and `BUG-254`: four times the bot's own order budget refused the bot's own order during a start, the refusal became `start_refused`, and the position was closed at market (real money; 0.13–0.14 USDT on `BUG-254`'s two starts). Every gate was green each time, and each fix closed the one instance the owner's money had found.

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| Grid journeys on the fake exchange | `app_config` sets `min_order_spacing_ms` to 0, so no journey met the spacing; `BUG-241` found it and added a `limits` option that only the journeys written for the fix used | no — `test_start_journeys_run_at_production_pacing.py` requires one per venue |
| `BUG-238`'s pacing journey | its stamp lag was equal for every order (`early_stamp_lag`: "the spacing between two consecutive orders is never shortened by it"), so the one case that shortens it was excluded | no — `VirtualTime.stamp_jitter` |
| The pacer's unit tests | the pacer was checked against its own clock, never against the clock that judges (trading stamps after the turn, `handler.py` `datetime.now`) | no — the verdict now decides, not the forecast |
| The classification `REFUSED` | `BUG-238` decided "no safety net maps a residual `owner_budget_*` to a pause", so a rule enforced twice (pacer, policy) stayed enforced twice, with the second terminal | no — `pacing_outcome` |

## The fix
- `tests/unit/architecture/test_start_journeys_run_at_production_pacing.py`: Spot (`booted`) and Futures (`booted_futures_bots`) each have a journey with `pacers=` and `limits=PRODUCTION_PACING`, read off `DEFAULT_OWNER_BUDGET_CAPS`.
- `tests/integration/modules/bots/test_a_burst_of_orders_is_not_refused_by_the_budgets_spacing_on_the_fake_exchange.py`: the start (screen and host door) under uneven stamps.
- `order_outcome.py` `pacing_outcome` and `paced_send.py`: the app's own pacing is "not yet"; the decision is `Tasks/epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-21_a_pacing_refusal_from_the_apps_own_budget_is_never_terminal.md`.

## Where else this is still open
- The other bots journeys run at no spacing by default (`grid_fake_exchange.app_config`); only the guarded ones meet the caps.
- A rule judged in two places (the plan's liquidation estimate against the start's, `BUG-255`) has the same shape.
