# EPIC-035L — Range exit, and Start with the price outside the range

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding H7 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz). Owner decisions of 2026-10-08: **D2** — stop-loss stays optional, no default and no forced warning; **D4** — option (a): price below the lower bound is REFUSED at Start, price above the upper bound is a WARNING and Start is allowed (see the [decision record](../DECISION_2026-10-08_spot_grid_audit_owner_decisions.md)).
**Risk:** 🟡 — a new refusal can block a Start the owner expected to work; the rule is narrow and named
**Complexity:** M — two verdicts, their wording in the Plan panel, one alert, SPEC
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task
**Depends on:** [EPIC-036B](../../EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md) (which superseded the cancelled [EPIC-035K](../cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md)) for the range-exit alert only; the two Start verdicts depend on nothing and may land first as their own PR

---

## 1. Context and problem
Audit H7 (a static finding; re-verify before coding): there is no domain reaction to a range exit, and Start with the price below the range market-buys the entire capital — the only verdict today is the informational `OK` / `OPENING_BUY` from `check_opening_buy` (`src/modules/bots/domain/grid/grid_account_checks.py:69-86`), which says the SELL levels' base is bought at market "out of the capital" and raises no objection. The verdict machinery already has the shape needed: `grid_checks.py` builds `Verdict(REFUSED | WARNING | OK, code, text, numbers)` and `check_price_band` (`src/modules/bots/domain/grid/grid_checks.py:148-190`) is an existing example of a refusal on the price. Other cited places: `src/modules/bots/domain/grid/grid_plan.py:127-131` (the opening buy), `src/modules/bots/ui/kinds/grid/grid_panel.py:166` (how a verdict reaches the panel).

Geometry to confirm in the first test: when `last_price` is below `lower`, every level is a SELL level, so the plan's opening buy covers the whole ladder's base — the full capital at market, at a price below the range the user designed for. Above `upper` every level is a BUY level: nothing is bought at Start and the bot waits for a fall, which is why it is a warning and not a refusal.

## 2. Acceptance criteria
- [x] **Refusal (D4a):** a plan whose `last_price` is **below the lower bound** produces a `REFUSED` verdict, code `PRICE_BELOW_RANGE` (name to be confirmed in the PR), which blocks Start through the same path as every other refusal. At exactly the lower bound it is not refused (the boundary is stated in the test).
- [x] **Warning (D4a):** a plan whose `last_price` is **above the upper bound** produces a `WARNING` verdict, code `PRICE_ABOVE_RANGE`, and Start is allowed. At exactly the upper bound there is no warning.
- [x] **Wording** (English, UI strings per `ONBOARDING.md` §10), each naming the figures and the next action:
  - Refusal: "The price {price} is below the range's lower bound {lower}. Starting now would buy about {quote} {quote_asset} of {base_asset} at market, the whole capital. Lower the range to include the price, or wait for it to return."
  - Warning: "The price {price} is above the range's upper bound {upper}. The bot starts with nothing bought and places BUY orders only; it trades once the price falls into the range."
- [x] The two verdicts reach the user before the click: in the Plan panel next to the price and range fields, visible without scrolling (the lesson of `EPIC-035N`), and in the Start button's disabled reason for the refusal (`EPIC-034H`'s single readiness query). *Verified through the existing mechanisms*: every constraint is judged by the one table the screen, the Start handler and the readiness query share, and `FIELDS_OF_CODE` puts each code on its fields; no panel code changed. Not looked at on a real screen.
- [x] **D2 holds:** no "stop-loss is off" warning is added and no stop-loss default changes. A test fails if either appears.
- [x] **Range exit while running:** once `EPIC-036B` exists, a price leaving the range (above or below) sends one alert, re-armed when the price returns; the bot's behaviour does not change (no automatic exit; D2).
- [x] `check_opening_buy`'s `OPENING_BUY` text stays accurate for a price inside the range.
- [x] `Docs/SPEC/SPEC-014_run_a_grid_bot.md` lists the two verdicts in its journeys.

## 3. Design
- **Where:** two new pure checks in `src/modules/bots/domain/grid/grid_checks.py`, registered in the same list the other checks use (so the screen, the Start handler and the readiness query read one verdict set — the single-readiness-query rule of `EPIC-034H`). No new layer, no UI logic. They take `GridCheckInputs` (`grid_check_inputs.py`), which already carries the plan, its `last_price` and the range.
- **Why a refusal below, a warning above:** below the range the plan buys the whole base at market before laying any order; above it nothing is bought and the exposure is zero. The asymmetry is the owner's decision (D4a), not a modelling shortcut.
- **Why no automatic exit on range exit:** D2 leaves stop-loss to the owner; the alert tells them, the bot does not decide for them.
- **Boundary and tick rounding:** compare the price with the *rounded* bounds the plan actually uses (`EPIC-035S` may refuse collapsed levels separately).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_checks.py` | `check_price_below_range` (REFUSED) and `check_price_above_range` (WARNING), registered with the other checks |
| `src/modules/bots/ui/kinds/grid/grid_panel.py` and the readiness reasons | Show both verdicts beside the price and range, and the refusal as Start's disabled reason |
| `src/modules/bots/application/` (the alert hook of `EPIC-035K`) | Range-exit alert, once per exit, re-armed on return |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The two verdicts and the alert |
| `tests/unit/modules/bots/domain/grid/test_grid_checks.py` and the readiness / presenter tests | The tests in §5 |

## 5. Testing (as planned)
Tier per `ci-rule.md` §2. The two grid-check tests are written first and shown **red on `3bbe243`'s behaviour** (no such verdict exists, so a plan below the range is not refused).

| Criterion | Test | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Refusal below | `tests/unit/modules/bots/domain/grid/test_grid_checks.py::test_a_price_below_the_lower_bound_is_refused` — red before: the plan's verdicts hold only `OPENING_BUY` (OK) | Unit | `Verdict(REFUSED, "PRICE_BELOW_RANGE", …)` with the price, the bound and the opening-buy figure in `numbers` |
| Boundary below | `test_a_price_exactly_at_the_lower_bound_is_not_refused` | Unit | No `PRICE_BELOW_RANGE` |
| Warning above | `test_a_price_above_the_upper_bound_warns_and_does_not_refuse` — red before: no verdict | Unit | `WARNING`, `PRICE_ABOVE_RANGE`; the plan's overall verdict is not REFUSED |
| Boundary above | `test_a_price_exactly_at_the_upper_bound_does_not_warn` | Unit | No warning |
| Inside | `test_a_price_inside_the_range_has_neither_verdict` | Unit | Neither |
| Wording | `test_the_range_verdicts_name_the_figures_and_the_next_action` | Unit | The texts above, with numbers |
| Start blocked | the readiness / start-handler test: a draft bot below the range cannot Start and the reason is shown | Unit (application) | Start refused with the verdict's text; same answer from the screen's query |
| Visible | presenter test: both verdicts appear beside the fields | Unit (ui) | Present without scrolling |
| D2 guard | `test_no_stop_loss_warning_and_no_default_stop_loss` | Unit | Absent |
| Range-exit alert | `test_a_range_exit_alerts_once_and_rearms` (after `EPIC-035K`) | Unit with a fake notifier and clock | One alert per exit; re-armed on return |

## Implementation notes
Re-verified against `master-warrior` `d563c0f` before coding. The audit's claim holds: before this task a plan below the range produced only the informational `OPENING_BUY` (OK) from `check_opening_buy` (`src/modules/bots/domain/grid/grid_account_checks.py:69-86`), and no code reacted to the price leaving the range. Cited lines drifted a little (`grid_checks.py` is longer than the task says; `check_price_band` is at `:148`).

- **Verdicts.** One check, `check_price_against_range` (`src/modules/bots/domain/grid/grid_range_checks.py`), answers `PRICE_BELOW_RANGE` (REFUSED), `PRICE_ABOVE_RANGE` (WARNING) or `PRICE_IN_RANGE` (OK), registered as the constraint `price_suits_the_range` in `grid_constraints.py`, so the screen, `GridKind.validate` and the readiness query read one verdict set. `D7`'s table says it blocks below and advises above, and `test_grid_constraints.py` holds that.
- **Bounds.** The check compares with the user's `lower` and `upper`, not the tick-rounded level prices the task suggested. The plan classes a level BUY or SELL by its *raw* price against the last price (`grid_plan.py`, `_side`), so the raw bounds are exactly where the plan changes shape; a price on a bound is inside (tested both sides of both bounds). `range_position.py` is the one definition, shared by the check and the running watch.
- **Wording.** The task's sentence names the base asset; `GridCheckInputs` carries no symbol, and adding one to every kind's inputs for a sentence was out of scope, so the text says "the base asset" and gives the share of the capital (the nearest level stays EMPTY within half a step, so it is not always 100%).
- **Running bot.** `GridRangeWatch` (`application/services/grid_range_watch.py`) is fed by `GridPriceReaction.on_tick` with the same `PriceTick` the stop loss reads (`BUG-191`); there is no second price path. It publishes `BotRangeChangedEvent(bot_id, symbol, position, price, lower, upper)` (`contracts/events/bot_range_changed_event.py`) once per change of place, and `INSIDE` on the return. It judges by the close, not by the wick: a pierced bound with the close inside is not an exit (tested). It watches in the states that watch exits and resets otherwise. It starts from INSIDE, so a bot started above the range (allowed, D4) is reported by its first tick.
- **Wiring.** `GridRunContext.events` and `GridExecutorDeps.events` (the bus's `IEventPublisher`), bound in `composition/executor_bindings.py`. `GridExecutor` gained no public member (`test_grid_executor_surface.py` green).
- **D2.** No stop-loss warning and no default were added (`test_no_stop_loss_warning_and_no_default_stop_loss`).
- **One existing test changed deliberately:** `test_the_refusals_are_the_exchange_and_money_rules_only` lists the refusals a set of plans may produce; one of its plans (price 50 000, range 60 000–70 000) is now correctly `PRICE_BELOW_RANGE`, which joined the set.

## 5b. Testing — evidence
Red first, at `d563c0f`'s behaviour: 15 of the new and changed unit tests failed (no such verdict), and `test_grid_range_exit.py` failed at collection (no such event). Green after. Mutations measured: dropping `self._range.note(tick)` fails 5 of the 10 range-exit tests; moving the lower boundary from `<` to `<=` fails `test_a_price_exactly_at_the_lower_bound_is_not_refused` and the running-bot bound test.
- `tests/unit/modules/bots/domain/grid/test_grid_range_checks.py` (verdicts, boundaries, wording, D2)
- `tests/unit/modules/bots/domain/grid/test_grid_constraints.py` (the new codes block or advise as D4 says)
- `tests/unit/modules/bots/application/test_start_bot_readiness.py` (below refused with the screen's words and no order; above starts)
- `tests/unit/modules/bots/application/services/test_grid_range_exit.py` (once per exit, re-armed, direct BELOW→ABOVE, bounds, wick, at rest, with a stop loss)
- `tests/unit/modules/bots/ui/kinds/test_grid_field_errors.py` (every code has its fields)

## Follow-up
- **`EPIC-036B`:** `BotAlertSource` subscribes to `BotRangeChangedEvent` and maps `BELOW`/`ABOVE` to `RANGE_EXIT` and `INSIDE` to its recovery; the once-per-exit and re-arm semantics are already in the event stream. No notifier is built here.
- Not looked at on a real screen: the two verdicts beside the Lower and Upper fields.

## Resume
Done. Delivered in the EPIC-035L/035S pull request.
