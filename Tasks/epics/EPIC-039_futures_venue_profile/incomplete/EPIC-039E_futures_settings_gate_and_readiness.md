# EPIC-039E — A Futures bot starts only on a venue whose leverage, margin type and mode match its parameters, and readiness speaks in Futures facts

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §3, §7](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — it writes account-wide settings on a real venue; refusals must be exact
**Complexity:** M — a gate, a facts generalisation, a drift rule
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (readiness words); [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md) (the order session) is read.
**Design:** [DESIGN §3, §7](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§3, §8](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** D3, O5
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
- [ ] `IVenueSettingsGate.ensure(request) -> GateResult` (a port in `bots/contracts`; Spot adapter: no-op `ENSURED`; Futures adapter over `IFuturesSettingsControl`): reads the symbol's setting and the account's position mode, refuses `HEDGE_MODE_UNSUPPORTED`, sets margin type then leverage **only if they differ**, **reads back**, and answers `ENSURED` or a named refusal carrying both values (`SETTINGS_MISMATCH: leverage 3 asked, exchange says 5`). It never changes position mode.
- [ ] The gate runs **before any order** and refuses to run its writes with an open order or position on the symbol (the exchange refuses; the gate says why in words instead of passing a raw `-4xxx`); the recorded Binance page for leverage and margin type is cited in the notes, including whether leverage can change with orders open.
- [ ] `IVenueFacts` generalises `ExchangeFacts`: Spot adapter returns today's `ExchangeFacts` **unchanged** (the Spot readiness tests pass untouched); Futures adapter returns `FuturesFacts` (`available_margin`, `position` (signed, from `positionRisk`), `position_mode`, `symbol_setting`, `bracket_for(notional)`, `own_open_orders`, `foreign_open_orders`, `foreign_position`, `earlier_runs` analogue, `can_trade`, read-at). Same three states (checking / unavailable / loaded); an unreadable fact is never zero.
- [ ] Futures readiness rules (in `exchange_rules`' style, one function each, listed in a `FUTURES_RULES` tuple): `MARGIN_SHORT_FOR_LADDER` (initial margin for the plan's worst case vs available margin), `FOREIGN_POSITION`, `LEVERAGE_ABOVE_BRACKET`, `POSITION_MODE_NOT_ONE_WAY`, `SYMBOL_NOT_TRADING` (exists: reuse), `KEY_CANNOT_TRADE` (exists: reuse). Spot rules do not run on Futures and vice versa — chosen by profile, not by a branch inside a rule.
- [ ] **Drift:** `reconcile_after_gap` (and the periodic check) re-reads the setting; a changed leverage or margin type halts the bot with `GridReason.SETTINGS_DRIFT` naming both values; the halt follows the Futures halt policy (039H/039L), not a silent re-set.
- [ ] `AccountView` is generalised or paired with `MarginView` so the Connect step can show available margin for a Futures venue; the Spot field and its UI words are unchanged.
- [ ] Hedge Mode on a Futures account makes the Connect step say so (existing words) and blocks Start.
- [ ] A settings change the gate made is logged at INFO with the venue, symbol, old and new values `[futures-gate]`.

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
Not run yet.

## Pitfalls
- `positionRisk` v3 has **no** leverage or margin type (`BUG-114`): read them from `symbolConfig` via `FuturesSymbolSetting`.
- Changing margin type or leverage on a symbol that has a position or orders is refused by the exchange: order of operations matters (gate first, flat symbol).
- Position mode is account-wide: never change it from a bot; another bot or the owner's manual desk may be using the account.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: read Binance's Change Initial Leverage and Change Margin Type pages (RESEARCH §8) and record their rules here.
