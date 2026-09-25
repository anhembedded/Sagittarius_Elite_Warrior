# BOT-105C — Partial Take Profit (scale-out) closes a fraction of a position at each configured level

**Status:** ✅ Done (2026-09-25)
**Source:** `BOT-105A` §3/§4 deferred this explicitly ("Partial TP vẫn hoãn, backlog riêng khi cần") rather than bundling it into Break-Even/Trailing Stop; the user's "Next" instruction after `PR #266` (BOT-105A Trailing Stop) merged picked this up as the epic's one remaining mechanism.
**Risk:** 🟡 — touches the realized-PnL formula's calling convention (`MarginRiskPolicy.calculate_realized_pnl()`); a proration mistake would misstate cash balance across multiple partial exits from the same position.
**Complexity:** M — one new value object, one new `PaperExchange` mechanism reusing the existing `FillPricing`/`MarginRiskPolicy` primitives; no new formula.
**Epic:** [`BOT-105`](../backlog/BOT-105_advanced_order_execution_and_risk_epic.md) — the last of its 5 sub-mechanisms.
**SPEC (optional):** None
**Depends on:** [`BOT-105A`](BOT-105A_trailing_stop_and_partial_tp.md) (Break-Even/Trailing Stop, done), [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) (`take_profit_pct` — mutually exclusive with this task's levels)

---

## 1. Context and problem

`BOT-105A`'s own notes (§3) already established why Partial TP could not ride along with Break-Even/Trailing Stop: those two only ever move `stop_loss_price` on an already-whole position, while Partial TP must close part of a position and keep the rest open — `_close_one_position()` (`paper_exchange.py:300`) always closes the whole `pos.quantity` and removes the position from `self._positions`, and `Trade`/`OpenPosition.quantity` currently stand for one indivisible position. Splitting quantity away from "closing the position" is exactly the "cấu trúc sâu hơn" the deferral named.

## 2. Acceptance criteria

- [x] A `BrokerSimulationConfig` field configures an ordered list of scale-out levels — each a `(price_pct, close_fraction)` pair, `price_pct` the same %-distance-from-entry convention as `stop_loss_pct`/`take_profit_pct`, `close_fraction` the fraction of the ORIGINAL entry quantity to close at that level.
- [x] When a bar's high (LONG) / low (SHORT) reaches a level's price, `PaperExchange` closes exactly that level's fraction of the original quantity, realizes its PnL, appends a partial `Trade` tagged with a new `ExitReason`, and leaves the remainder open.
- [x] Financial invariant: total closed quantity across all partial exits plus the quantity remaining open always equals the original entry quantity (exactly, not approximately, since each level's absolute close quantity is fixed at entry time).
- [x] Financial invariant: cash balance after a partial exit reflects that exit's prorated share of `entry_fee`/`balance_before_entry` — never the whole position's.
- [x] A position whose last configured level exactly exhausts its quantity is removed from open positions (no zero-quantity ghost).
- [x] Two-level (TP1/TP2) scale-out test proves both exits and the correct residual state.
- [x] Levels are mutually exclusive with the existing single `take_profit_pct` (undefined interaction otherwise) and mutually exclusive-checked ordering/sum validation at construction.

## 3. Design

- **`PartialTakeProfitLevel`** (new frozen dataclass, `contracts/partial_take_profit_level.py`): `price_pct: float` (>0), `close_fraction: float` (`0 < x <= 1.0`). Mirrors `stop_loss_pct`'s validated-percent convention; kept as its own file per `architecture-rule.md` §5 (a value object is its own abstraction level, same reasoning as `PositionSizing`).
- **`BrokerSimulationConfig.partial_take_profit_levels: tuple[PartialTakeProfitLevel, ...] = ()`**: empty tuple (not `None`) since it is a collection — `()` is already the "disabled" state, no second sentinel needed. Validated: `price_pct` strictly increasing across levels (sequential, unambiguous triggering order), `sum(close_fraction) <= 1.0`, and mutually exclusive with `take_profit_pct` (both configure "how this position takes profit"; combining them is a semantics this task was never asked to define).
- **Absolute levels precomputed once at entry**, mirroring `stop_loss_price`/`take_profit_price`: `OpenPosition` gains `partial_take_profit_prices: tuple[float, ...]` and `partial_take_profit_close_quantities: tuple[float, ...]` (the latter is the ORIGINAL quantity times each level's `close_fraction`, fixed at `_open()` time so the "closed + remaining == original" invariant needs no separately-tracked original-quantity field), plus `partial_tp_next_level_index: int = 0` tracking progress (levels fire in order; a level already hit is never re-evaluated).
- **`FillPricing.partial_take_profit_prices()`**: a new thin wrapper forwarding to `OrderMatchingPolicy.calculate_take_profit_price()` per level with that level's own `price_pct` (that method already takes an explicit `pct` argument — no change needed there), mirroring the existing `take_profit_price()` wrapper's shape.
- **Proration, the core financial mechanism**: `MarginRiskPolicy.calculate_realized_pnl()` already takes `quantity`/`entry_fee`/`balance_before_entry` as plain arguments (not read off the position), so a partial close passes `close_qty` for quantity and `pos.entry_fee * fraction` / `pos.balance_before_entry * fraction` for the other two, where `fraction = close_qty / pos.quantity` (the position's CURRENT remaining quantity at the time of this exit, so a second partial exit prorates correctly against what actually remains after the first). After the call, `pos.quantity`, `pos.entry_fee` and `pos.balance_before_entry` are all reduced by that same fraction — keeping the three mutually consistent for the next exit (full or partial) to prorate against. No change to `calculate_realized_pnl()` itself: it is already generic over "how much of what is being realized," exactly like a full close is `fraction = 1.0`.
- **New `PaperExchange._close_partial_position()`**: sibling to `_close_one_position()`, not a shared refactor of it — a partial close mutates the position in place and returns one `Trade`, a full close removes it from `self._positions`; forcing one method to do both would need a boolean-flag argument, which `code/quality.md` §7 forbids. The duplication is the `Trade` construction and log line, already small.
- **New `PaperExchange._apply_partial_take_profits()`**: checked LAST in `check_intrabar_stops()`, after liquidation/stop-loss/take-profit evaluation removes their own closes from `self._positions` — a position that already fully closed this bar via liquidation or its stop/TP never also produces a partial-TP trade the same bar, applying this codebase's existing pessimistic-first convention (`BOT-041`/`BOT-105B`) without inventing a new tie-break mechanism for a rare same-bar ambiguity.
- **New `ExitReason.PARTIAL_TAKE_PROFIT`**: a partial exit is a distinct trading fact from a full `TAKE_PROFIT` close (`domain-truth-rule.md` — "distinct trading facts"), and a report/metrics consumer must be able to tell them apart (a partial exit's `Trade.quantity` is not the position's entry quantity).
- **Scale-out semantics chosen**: each level's `close_fraction` is a fraction of the ORIGINAL entry quantity, not of what remains after a prior level (so `50%` + `50%` fully closes at the second level, matching how most venues describe "sell 50% of your position at TP1, the rest at TP2" — a compounding remainder-of-remainder reading was rejected as less predictable and unsupported by the task's own example). Documented here since the original spec's phrasing was ambiguous on this point, same as Trailing Stop's unit choice was documented in `BOT-105A` §4.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `contracts/partial_take_profit_level.py` | New: `PartialTakeProfitLevel` value object + validation. |
| `contracts/broker_simulation_config.py` | New `partial_take_profit_levels` field + ordering/sum/mutual-exclusion validation. |
| `contracts/exit_reason.py` | New `PARTIAL_TAKE_PROFIT` member. |
| `domain/open_position.py` | New `partial_take_profit_prices`, `partial_take_profit_close_quantities`, `partial_tp_next_level_index` fields. |
| `domain/fill_pricing.py` | New `partial_take_profit_prices()` wrapper. |
| `domain/paper_exchange.py` | `_open()` precomputes the two new tuples; new `_close_partial_position()`/`_apply_partial_take_profits()`; wired at the end of `check_intrabar_stops()`. |
| `tests/unit/modules/backtesting/contracts/test_broker_simulation_config.py` | Validation tests for the new field. |
| `tests/unit/modules/backtesting/domain/test_paper_exchange.py` | Single-level, two-level (TP1/TP2), invariant, same-bar-as-liquidation/stop precedence tests. |

## 5. Testing

Unit tier only (`tests/unit/modules/backtesting/`) — same tier as every other `BOT-105` mechanism; no integration/sanity change since nothing crosses a process boundary.

## Implementation notes (written when done)

All 7 acceptance criteria met exactly as designed in §3 — no changes needed
mid-implementation:

- `PartialTakeProfitLevel` (`contracts/partial_take_profit_level.py`),
  `ExitReason.PARTIAL_TAKE_PROFIT`, `BrokerSimulationConfig.
  partial_take_profit_levels` (+ ordering/sum/mutual-exclusion validation),
  `OpenPosition.partial_take_profit_prices`/`partial_take_profit_close_
  quantities`/`partial_tp_next_level_index`, `FillPricing.
  partial_take_profit_prices()`, `PaperExchange._close_partial_position()`/
  `_apply_partial_take_profits()` — all built exactly per §3/§4.
- **One thing the design didn't anticipate**: `EnumLabels` in
  `trade_log_row.py` raises at import time for any `ExitReason` member
  without a UI label (by design — `domain-truth-rule.md`'s "truthful UI",
  no silent fallback), which the new enum member tripped immediately —
  caught by running the full `tests/unit/modules/backtesting` suite, not
  by the domain-focused `test_paper_exchange.py` alone. Added a label
  ("Partial Take Profit (scale-out)") and, in `chart_canvas_view.py`,
  a distinct short code ("pTP", never "TP" — a different trading fact per
  `domain-truth-rule.md`) and extended `_exit_marker()`'s take-profit
  color/label branch to cover it, since a partial exit genuinely is
  profit-taking and deserves the same visual family as a full
  `TAKE_PROFIT`, just distinguishable by its short code and by
  `Trade.quantity` being a fraction of the position.
- **Scale-out semantics** (documented in §3, confirmed unchanged):
  `close_fraction` is a fraction of the ORIGINAL entry quantity, not of
  what remains — two 50% levels fully close a position at the second
  level, matching the task's own "sell 50% at TP1, 50% at TP2" example.
- **Proration verified by hand** (`test_partial_take_profit_closes_each_
  level_and_leaves_the_remainder_open`): entry 100, qty 10, zero
  commission. TP1 at 105 closes 5 (pnl 25, balance 525); TP2 at 110 closes
  the remaining 5 against its own already-reduced `balance_before_entry`
  (500, not the original 1000) — pnl 50, final balance 1075. Confirms the
  fraction-of-current-remaining proration in `_close_partial_position()`
  produces correct, additive PnL across sequential partial exits without
  double-counting or under-counting the entry fee/margin.
- **Precedence verified** (`test_partial_take_profit_never_fires_the_same_
  bar_a_static_stop_loss_closes_it`): a bar spanning both a static
  stop-loss and a partial-TP level closes as `STOP_LOSS` only — partial-TP
  runs last in `check_intrabar_stops()`, after liquidation/SL/TP already
  removed the position.
- `paper_exchange.py` grew from 460 to 587 lines — `BOT-144` (the existing
  400-line debt tracker) updated to reflect the new size and the two new
  methods as part of its already-tracked extraction target; no new
  refactor done in this PR, same call this repo made for `PR #266`.

**Mutation-verified**: temporarily removed the `_apply_partial_take_profits()`
call from `check_intrabar_stops()` — 2/9 new tests went red for the right
reason (the two tests that actually exercise a level triggering); restored
after confirming.

**Verification**: `ruff check`/`ruff format --check` clean on every changed
file. `MYPYPATH=/tmp/engine .venv/bin/mypy --config-file pyproject.toml
--namespace-packages --explicit-package-bases src scripts` (run from the
parent directory, the gate-faithful invocation): zero errors in any file
this task touched. `tests/unit/modules/backtesting/domain/test_paper_
exchange.py`: 95 passed (+9). `tests/unit/architecture`: 440 passed.
`tests/unit/modules/backtesting` (whole module, including UI): 970 passed
(961 baseline + 9 new), no regressions.
`python3 scripts/check_skill_prompt_references.py`: OK.

**Delivery**: committed, pushed, `PR #267` opened, independently reviewed
(verdict PASS, full 97-Check-ID rubric disclosed) and merged to
`master-warrior` by the user (2026-09-25).

**Follow-up from independent review of `PR #267`** (1 non-blocking
observation, not a confirmed defect): `_apply_partial_take_profits()`
removed fully-closed positions from `self._positions` with `[p for p in
self._positions if p not in fully_closed]` — since `OpenPosition` is a
mutable (non-frozen) dataclass, `in` here is VALUE equality across every
field, not identity, unlike this file's other position-list rebuilds
(`_close()`'s `pos.side is not side`, `evaluate_liquidations()`/
`evaluate_intrabar_stops()` appending references). The reviewer built a
repro (two field-identical pyramided `BUY` entries, one partial-TP level)
and confirmed both twins stayed correctly open — no reachable collision,
because a position only enters `fully_closed` once `quantity` hits exactly
`0.0`, and a genuinely still-open position always has `quantity > 0`, so
the discriminating field can never coincide. Fixed anyway as a hygiene/
consistency correction (identity via `id()`, matching the rest of the
file) since the old code worked only by an invariant not enforced at that
call site. No regression test was added for this one: per
`testing-rule.md` ("do not test states an invariant already makes
unreachable"), the collision cannot be constructed without breaking that
same invariant, so no test could meaningfully fail under the old code —
confirmed by re-running the existing suite unchanged and green.

Re-verified after the fix: `ruff check`/`format --check` clean; mypy zero
errors in `paper_exchange.py`; `test_paper_exchange.py` 95 passed
(unchanged, no new test needed per the above); full `tests/unit` suite
green (see the follow-up commit's own PR for the exact re-run).
