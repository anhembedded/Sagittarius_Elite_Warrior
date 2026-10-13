# EPIC-039E — A Futures bot starts only on a venue whose leverage, margin type and mode match its parameters, and readiness speaks in Futures facts

**Status:** ✅ Done (2026-10-13)
**Source:** the owner, 2026-10-10; [DESIGN §3, §7](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — it writes account-wide settings on a real venue; refusals must be exact
**Complexity:** M — a gate, a facts generalisation, a drift rule
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (readiness words); [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md) (the order session) is read.
**Design:** [DESIGN §3, §7](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§3, §8](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** D3, O5
**Branch:** `claude/epic-039e-settings-gate`
**Depends on:** [039A](EPIC-039A_venue_profile_seam.md).

---

## 1. Context and problem
A Futures symbol has a leverage and a margin type, and the account has a position mode. The bot's parameters name a leverage and a margin mode; the venue must match before the ladder is laid, and must be *proved* to still match later. Readiness (`ExchangeFacts`, `exchange_rules.py`) speaks only Spot: base and quote balances, "base short for sells", "quote short for the ladder".

### Facts verified on `master-warrior` `076d339`
- `trading/contracts/i_futures_settings_control.py`: leverage and margin-type setters answering what the exchange confirmed or why it refused; on Spot every change answers `AccountControlRefusal.NOT_A_FUTURES_VENUE`; position mode is listed as a "plausible extension", **not built**. `VenueTradingPorts.futures_settings` is the handle.
- `trading/contracts/futures_symbol_setting.py` (`leverage`, `margin_type`, `max_notional`); `leverage_setting.py`; `leverage_brackets.py`; `i_order_entry_terms.py` reads them (`NotApplicable.ON_THIS_VENUE` on Spot).
- The connection check refuses Hedge Mode: `ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED` (words in `bots/application/services/connect_failure_words.py:52`, `trading/ui/settings/connection_state_words.py:53`).
- Binance (opened): position mode is account-wide, shared UM/CM, rejected with open orders (`-4067`) or positions (`-4068`) (RESEARCH §3). Leverage and margin-type pages **did not render** (RESEARCH §8): read them first.
- Readiness: `bots/contracts/exchange_facts.py` (`ExchangeFacts`: `base_free/locked`, `quote_free/locked`, `own_sell_base`, `own_buy_quote`, `own_open_orders`, `foreign_open_orders`, `earlier_runs`, `can_trade`; states `ExchangeChecking`/`ExchangeUnavailable`/`ExchangeLoaded`), `application/services/exchange_facts_reader.py` (reads `SpotHolding`s), `exchange_rules.py` (`RULES`, `judge_exchange`, `base_short_for_sells:201`, `quote_short_for_ladder:229`), `bot_exchange_terms.py`.
- `AccountView.available_quote` (`domain/bot_kind_inputs.py`) — what a new order can spend; Futures has *available margin*.

## 2. Acceptance criteria
- [x] `IVenueSettingsGate.ensure(request) -> GateResult` (a port in `bots/contracts`; Spot adapter: no-op `ENSURED`; Futures adapter over `IFuturesSettingsControl`): reads the symbol's setting and the account's position mode, refuses `HEDGE_MODE_UNSUPPORTED`, sets margin type then leverage **only if they differ**, **reads back**, and answers `ENSURED` or a named refusal carrying both values (`SETTINGS_MISMATCH: leverage 3 asked, exchange says 5`). It never changes position mode.
- [x] Handed over by [039C](../completed/EPIC-039C_futures_fake_exchange_matching.md) (2026-10-13): the fake now refuses what Binance's error-code page says it refuses - margin type with open orders `-4047` or a position `-4048`, an isolated leverage reduction with a position `-4161`, position side with orders `-4067` or a position `-4068`, an order past the leverage's notional `-2027` or the margin `-2019` - and `POST /fapi/v1/positionSide/dual` exists. The gate's tests can use them. The REST pages for Change Initial Leverage, Change Margin Type and the brackets were **not** in the docs index that was reachable (`llms-full.txt` holds the general pages only): read them before relying on a field name.
- [~] *(built; the call in Start is 039H's - nothing calls `ensure` yet)* The gate runs **before any order** and refuses to run its writes with an open order or position on the symbol (the exchange refuses; the gate says why in words instead of passing a raw `-4xxx`); the recorded Binance page for leverage and margin type is cited in the notes, including whether leverage can change with orders open.
- [~] `IVenueFacts` generalises `ExchangeFacts`: Spot adapter returns today's `ExchangeFacts` **unchanged** (the Spot readiness tests pass untouched); Futures adapter returns `FuturesFacts` (`available_margin`, `position` (signed, from `positionRisk`), `position_mode`, `symbol_setting`, `bracket_for(notional)`, `own_open_orders`, `foreign_open_orders`, `foreign_position`, `earlier_runs` analogue, `can_trade`, read-at). Same three states (checking / unavailable / loaded); an unreadable fact is never zero.
- [x] Futures readiness rules (in `exchange_rules`' style, one function each, listed in a `FUTURES_RULES` tuple): `MARGIN_SHORT_FOR_LADDER` (initial margin for the plan's worst case vs available margin), `FOREIGN_POSITION`, `LEVERAGE_ABOVE_BRACKET`, `POSITION_MODE_NOT_ONE_WAY`, `SYMBOL_NOT_TRADING` (exists: reuse), `KEY_CANNOT_TRADE` (exists: reuse). Spot rules do not run on Futures and vice versa — chosen by profile, not by a branch inside a rule.
- [x] **Drift:** `reconcile_after_gap` (and the periodic check) re-reads the setting; a changed leverage or margin type halts the bot with `GridReason.SETTINGS_DRIFT` naming both values; the halt follows the Futures halt policy (039H/039L), not a silent re-set.
- [x] `AccountView` is generalised or paired with `MarginView` so the Connect step can show available margin for a Futures venue; the Spot field and its UI words are unchanged.
- [~] *(refusal built in the gate and in readiness; "blocks Start" is 039H's wiring)* Hedge Mode on a Futures account makes the Connect step say so (existing words) and blocks Start.
- [x] A settings change the gate made is logged at INFO with the venue, symbol, old and new values `[futures-gate]`.

## 3. Design
A gate (precondition + postcondition: *ensure, read back, compare*) rather than a fire-and-forget setter: the exchange's answer to a change is what it *confirmed* (`LeverageSetting`), and the gate checks that against what the bot asked, so a silent difference cannot reach the first order. Facts are a sum type per profile behind one port (interface segregation: a Spot-only kind never sees margin). Rules are selected by profile from a table (open/closed), not branched on inside.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/contracts/i_venue_settings_gate.py`, `i_venue_facts.py`, `futures_facts.py` (new) | ports and values |
| `bots/application/services/venue_settings_gate_futures.py`, `venue_settings_gate_spot.py` (new) | adapters |
| `bots/application/services/exchange_facts_reader.py` | becomes the Spot adapter of `IVenueFacts` (the one allowlisted `SpotHolding` user from 039A leaves the guard's list) |
| `bots/application/services/futures_facts_reader.py`, `futures_rules.py` (new) | Futures readiness |
| `bots/application/services/grid_reconciler.py` (+ the drift check) | `SETTINGS_DRIFT` |
| `bots/domain/grid/grid_runtime.py` | `GridReason.SETTINGS_DRIFT` |
| `bots/domain/bot_kind_inputs.py` | margin view |

## 5. Testing
Tier: unit (gate with a fake `IFuturesSettingsControl`; rules), integration on the Futures fake (039C).
- `test_the_gate_sets_margin_type_then_leverage_and_reads_back` · `test_a_mismatch_after_readback_is_a_start_refusal_naming_both_values`
- `test_the_gate_refuses_with_an_open_order_on_the_symbol_in_words`
- `test_hedge_mode_blocks_start` · `test_the_gate_never_calls_a_position_mode_setter`
- `test_margin_short_for_the_ladder` · `test_foreign_position_is_a_readiness_refusal`
- `test_spot_readiness_results_are_unchanged` (the existing Spot tests, untouched)
- `test_changed_leverage_between_polls_halts_with_settings_drift`
Run: see the implementation notes.

## Pitfalls
- `positionRisk` v3 has **no** leverage or margin type (`BUG-114`): read them from `symbolConfig` via `FuturesSymbolSetting`.
- Changing margin type or leverage on a symbol that has a position or orders is refused by the exchange: order of operations matters (gate first, flat symbol).
- Position mode is account-wide: never change it from a bot; another bot or the owner's manual desk may be using the account.

## Implementation notes (written when done)
**Binance facts.** The REST pages for Change Initial Leverage and Change Margin Type are a script-built site: fetched with `curl -L` they answer `202` with an empty body, and the docs index `llms-full.txt` (65 KB from `developers.binance.com/docs/derivatives/llms-full.txt`) is the site shell, not the pages. They remain **unread**. What the gate relies on is the error-code page as `039C` recorded it (`-4047` margin type with open orders, `-4048` with a position, `-4161` an isolated leverage reduction with a position, `-4067`/`-4068` position side). **Whether leverage may change with orders open is not established**, so the gate assumes it may not and refuses *any* change on a symbol with an order or a position, in words; a setting that already matches is never written, so a Resume with its ladder resting passes. The owner's Futures testnet run is what checks this guess.

**Shape.** `IVenueSettingsGate` has two methods, `ensure` (precondition and postcondition: read, change only what differs, read back, compare) and `verify` (the read-only half a running bot uses). `VenueSettingsGates` and `VenueFactsByProfile` pick the Spot or Futures adapter by `VenueProfile.exposure_kind`, so no rule or caller names a market. The Futures gate reads the position mode from the connection check and never calls a position-mode setter (the control port has none).

**Findings the task text lacked.**
- **A leverage or margin change is signed account activity and needs the venue's order session open** (`trading_switch_off` otherwise; found by the first integration run). Start opens the session first; a closed one is `CHANGE_NOT_PERMITTED`, not an exchange refusal.
- **A Hedge account never reaches a loaded snapshot.** The connection check fails with `HEDGE_MODE_UNSUPPORTED` before the account summary is read, so `FuturesFactsReader` answers `ExchangeUnavailable` in the Connect step's own words (which is what blocks Start); `POSITION_MODE_NOT_ONE_WAY` is the rule for a loaded snapshot that says Hedge, kept because the facts type allows it.
- `exchange_facts_reader.py` left the `SpotHolding` list by reading balances into its own row type, so the guard's exception is gone and the type is forbidden everywhere in `bots`.
- `SYMBOL_NOT_TRADING` and `KEY_CANNOT_TRADE` already run on every profile as the kind's Design verdicts (`symbol_status_gate.py`, `grid_account_checks.py`); they are not repeated in `FUTURES_RULES`.

**Deviations from the criteria, and who owns the rest.**
- `FuturesFacts` has no `foreign_position` or `earlier_runs` analogue: whether some of a position is the bot's own needs the exposure book (**039D**). Until then `position` is the exchange's signed position and a *start* treats any position as foreign (a start owns none); a *resume* says nothing about it. The same holds for a resume's margin (the bot's resting orders hold some).
- `FUTURES_RULES` and `judge_venue` exist and are tested but no Futures flow calls them: `assess_readiness` still takes `LadderNeeds`, and the Futures `FuturesNeeds` (initial margin, worst-case notional, leverage) is built by the Futures executor (**039H**), which also binds `IVenueFacts` where the Grid reads readiness. Nothing runs on Futures in this build (`BOT_MARKETS`), so no behaviour changed for a user.
- "The periodic check" is the reconcile that already runs after a restart, a stream gap and a sleep (`compare_with_exchange`); there is no other periodic reconcile to hook. The halt policy for a Futures bot (**039H/039L**) is whatever a mismatch does today; the drift is only named.
- `MarginView`/`margin_view_of` exist beside `AccountView`; the Connect step's screen does not show them yet (**039J**).

**Shared files touched** (039D and 039G run in parallel): `grid_run_context.py` (+ `settings_check`), `grid_executor_factory.py` (+ `settings_gate` dep, defaulting to Spot's), `grid_reconciler.py` (+ the drift step), `grid_runtime.py` (+ `GridReason.SETTINGS_DRIFT`), `bot_kind_inputs.py` (+ `MarginView`), `exchange_rules.py` (`_item`/`_money` made public as `item`/`money`; `judge_exchange` now calls the shared `not_loaded_outcome`, behaviour unchanged), `executor_bindings.py` (three bindings), and the test helpers `grid_world.py` and `gap_world.py` (an optional `settings_gate`).

**Evidence.** Commit tier: `ruff check`, `ruff format --check` and `mypy` (src and scripts) clean; `check_skill_prompt_references.py` clean. `tests/unit` and `tests/integration/modules/bots`: 13 090 passed, 3 skipped; the only error is `tests/unit/scripts/test_ci_local_checkout_name_guard.py`, which needs `pwsh` (absent in this container; GitHub Actions has it). Mutations that turned the new tests red and were restored: dropping the drift step, dropping the read-back, writing every setting, dropping the flat-symbol check. The Spot readiness tests, `test_spot_sentences_are_pinned.py` and the architecture guards ran untouched and green. The `-Full` run is the pull request's.

## Resume
Done. Open items elsewhere: **039D** adds the position's own/foreign split and the resume margin; **039H** builds `FuturesNeeds`, binds `IVenueFacts` into readiness and decides what a drift halt does with the position (O8); **039J** shows `MarginView`. The owner's Futures testnet run checks the guess about leverage with orders open and the REST pages' field names.
