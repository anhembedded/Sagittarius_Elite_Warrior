# EPIC-025C — Phase 2: `modules/strategy` (the Core domain)

- **Status:** 🟡 Started 2026-09-16 — **PR 2.1a done** (the unblocking measurement and the one
  split it produced). The move itself, PR 2.1b, is next; §3 below is the cut, measured rather
  than estimated.
- **Repository:** Elite
- **Blocked by:** B · **Blocks:** D
- **Read first:** HLD §3.4; ADR D1 (`strategy` is the Core domain, separated from `trading` — the
  cost of keeping them merged was `BUG-112`).

## 1. What to do

1. `modules/strategy/`: `domain/strategies`, `services/live_strategy_*`, the
   `use_cases/trading/{arm, disarm}_strategy` handlers (moved out of trading),
   `StrategyArmingCoordinator` (392 lines, from `ui/common`), `signal_feed`.
2. `contracts/`: `IStrategyCatalog`, `IStrategyEngineFactory` (for `backtesting` in Phase 3), the
   DTOs `StrategyDescriptor` and `ArmedStrategySnapshot` (carrying `symbol`), the existing
   `SignalGeneratedEvent` (name unchanged) and the new `StrategyArmedEvent` / `StrategyDisarmedEvent`
   (carrying `symbol`).
3. `strategy` **consumes** `trading.contracts.IOrderSubmission` — never the reverse (Customer /
   Supplier: `trading` is the supplier). The symbol lease **adds to** the existing rules: `strategy`
   calls `ITradingSession.claim_symbol` on arm and `release_symbol` on disarm; `arm_strategy` still
   reads the session's enabled state. **Seam for two strategies on two symbols (ADR §7 item 15):**
   `LiveStrategySession` is keyed by symbol internally even while only one entry exists, so the
   second entry later is a local change. **ADR D17:** `position_sizing_bridge` and `MarginRiskPolicy` move here behind
   `strategy/contracts/ISizingPolicy`; `LiveTradingCoordinator` puts the computed quantity on the
   `OrderIntent`; the boundary-allowlist entry for `trading → backtesting` is removed in this phase. Signal overlays on
   the chart go through `IChartHost` (HLD §4).
4. Contributed widgets: the strategy card (one implementation shared by Trading and Dev Board), the
   last-signal card, the parameters dialog.

## 2. Done when

- The guard confirms that `modules/trading` imports **nothing** from `modules/strategy`, not even
  its `contracts/`.
- Arm / disarm / tick → automatic order runs on Testnet exactly as before (confirmed by the user).

---

## 3. The cut, measured 2026-09-16 before any code moved

`ls`-and-`grep` are not a measurement; these numbers come from walking the AST of every file in
`src/` and `scripts/`. **26 files / 2782 lines** would move under §1's list, with **13 consumer
files** naming them.

### 3.1 What the moving code reaches for that is not moving

| Dependency | Sites | What it means |
| :--- | ---: | :--- |
| `support.indicators.*`, `core.vo`, `core.contracts`, `modules.trading.contracts.*`, `support.ui_kit.*` | 44 | already permitted — nothing to unblock |
| `domain.value_objects.{signal_action,signal,live_strategy_config}` | 16 | strategy's own vocabulary; moves to `strategy/contracts` (HLD §02 line 89, §3.4) |
| `domain.events.signal_generated_event` | 2 | the same; the name stays (§1 item 2) |
| `application.services.live_trading_coordinator` | 2 | **not trading's, on measurement** — see §3.3 |
| `config.config_keys` | 1 | the legacy config keys module; Phase 5's |
| `presentation.ui.{common.strategy_display,components.strategy_params}` | 2 | strategy's UI; §1 item 4 |

### 3.2 Who reaches into it

13 files: `binance_bot_module.py` (10 imports — the strangler module still wires every strategy),
both big Presenters (4 each), the two backtest handlers, `trade_once_cmd`, `market_tick_event_handler`,
`backtest_presenter`, two `strategy_overlay` components, `strategy_params/bot_params_form.py`, and
two `scripts/` probes. Each becomes a counted `legacy → modules.strategy` allowlist entry when the
move lands and retires when its consumer moves onto a port — the shape `0.4a → 0.5` and
`1.3a → 1.3b` already ran twice, and the reason the allowlist header calls such a jump *"not a
regression"*. It is a different thing from the growth
[`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md) refused: there the
11 entries had **no** port to repay them before Phase 4, here every entry has a named repayment.

### 3.3 The finding: `trading` would have depended on `strategy`, and §2's done-when forbids it

`modules/trading/domain/policies/signal_action_to_order_intent.py` imports `SignalAction`. Move
`SignalAction` into `strategy/contracts` and that import becomes `trading → strategy` — which §2's
first done-when refuses outright, *"not even its contracts"*, and which ADR D1 separated the two
contexts to prevent.

Measured before deciding, and the file turned out to hold two unrelated things:

- `OrderIntent`, the `(side, reduce_only)` pair — **trading's own** vocabulary. Two producers
  (`order_intent_for()`, `manual_order_intent_for()`), and both consumers are *outside* the module,
  so by HLD §2.4's admission rule it already crosses the boundary.
- `order_intent_for()`, the `SignalAction → OrderIntent` table — **strategy's**, exactly what HLD
  §02 means by *"strategy only (plus trading through the bridge)"*. Its callers are
  `presentation/cli/trade_once_cmd.py` and `application/services/live_trading_coordinator.py`;
  **nothing inside `modules/trading` calls it.**

So `LiveTradingCoordinator` is strategy's too — it is the thing that turns a signal into an order,
and Customer/Supplier puts the translation on the customer's side — which also answers §3.1's
`live_trading_coordinator` row: it moves *in* rather than being reached for.

**PR 2.1a** therefore published `OrderIntent` as `modules/trading/contracts/order_intent.py` and
left the bridge where it is, ready to leave with its callers. Zero allowlist change, no behaviour
change, and it retired the naming compromise `order_request.py` and `Docs/SDD/05` both recorded:
`OrderRequest` was named around a collision with an `OrderIntent` in `domain/policies/`, and now
there is exactly one `OrderIntent` in the module, in `contracts/`, where HLD §3.4 always listed it.

### 3.4 The remaining pull requests

| PR | What | Allowlist |
| :--- | :--- | :--- |
| ~~2.1a~~ ✅ | `OrderIntent` published; the signal bridge identified as strategy's and isolated | unchanged (36) |
| ~~2.1b~~ ✅ | `modules/strategy/` arrives: 31 files / 2930 lines — `domain/strategies` (10), the seven services, `arm`/`disarm`, the bridge, `contracts/` for the four published types, and `module.py`. 19 test files / 140 tests moved with them, tier unchanged | **23 → 42**: 23 in, 4 retired (their files moved into the module), each new line naming the PR that deletes it |
| 2.1c | `IStrategyCatalog` published; `strategy_registry`'s consumers move onto it | shrinks |
| 2.1d | `ISizingPolicy` (ADR D17): `position_sizing_bridge` and `MarginRiskPolicy` move in; the `trading → backtesting` entry retires | shrinks |
| 2.1e | the UI: `strategy_arming_coordinator`, `signal_feed`, `strategy_display`, `strategy_params`, `strategy_overlay` → `modules/strategy/ui/`, with the strategy card contributed to both surfaces (§1 item 4) | shrinks |
| 2.1f | `ITradingSession.claim_symbol`/`release_symbol` — the lease `IOrderSubmission` shipped without, whose first consumer is `arm_strategy` (`Docs/SDD/05` §3) | unchanged |

`2.1e` is also where §3.1's `strategy_params` row is answered: HLD §3.5 assigns that package to
`support/indicators`, the rule table cannot satisfy it (`bot_params_form.py` needs `BaseStrategy`),
and a form rendering *a strategy's* parameters is `modules/strategy/ui`. That was recorded as open
for the user in `EPIC-025E`; Phase 2 existing is what makes it answerable, and the HLD row is fixed
in that pull request rather than left to disagree with the code.

---

## 4. PR 2.1b — what the move actually cost, and the two things it found

31 files / 2930 lines under `src/modules/strategy/`; 19 test files / 140 tests moved beside them
with the tier unchanged (ADR D7). `src/application/services/` is **gone** — all seven of its files
were this context's — and `src/domain/strategies/` with it. Allowlist 23 → 42. Duplicated members
unchanged at 59, as expected: that number moves when the two *screens* move, which
[`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md) put in Phase 2 +
Phase 4.

### 4.1 The rule table refused the move, and the rule was narrower than this design

`modules/strategy/domain/strategies/*` imports `EMA`, `IIndicator`, `MACDValue`,
`SupportResistance` and `scripting.Series` from `support/indicators` — and HLD §6.1 let a module
import a support package only through its `contracts/`. So the guard refused **14 imports across 8
files**, which is that package's entire public surface rather than a corner of it.

This is the third time in this epic that the table has been narrower than the HLD's own assignment,
and it was settled the way the first two were rather than with a second answer: the *imported* side
widened once, for one zone. A module may read `support/indicators`' four Qt-free sub-packages —
`indicators/`, `indicator_scripts/`, `scripting/`, `indicator_script_registry.py`, exactly the four
`test_module_domain_is_qt_free.py` already names — directly. The alternative was a
`support/indicators/contracts/` re-exporting five names for one consumer, which is the alias file
with no decision in it that PR 1.6f rejected for `Palette`.

Named rather than excluded, so a future `adapters/` under that package is refused by default. Six
edges pinned in `test_boundary_rules.py`, including the ones that must keep failing —
`modules/* → support/indicators/ui` above all, a module reaching for another package's
`QAbstractListModel`. Recorded in HLD §6.1.

### 4.2 Two defects the tests could not see, both found by the checks `ci-rule` §1 names

- **A test importing its own `conftest` by dotted path.** `test_support_resistance_strategy.py`
  read `from Sagittarius_Elite_Warrior.tests.unit.domain.strategies.conftest import …`, which the
  import rewriter never saw because the prefix was `tests.…` and not `src.…`. Collection error, not
  a failure — the whole unit tier refused to run. The all-modules import check is what surfaced it.
- **Four mypy exclusions keyed on the old path.** The same four strategy files have been frozen
  2026-08-21 debt in both `pyproject.toml`'s `exclude` list and a per-module override, keyed
  `src.domain.strategies.*`; the move made the keys stale and 29 errors resurfaced. Classified
  before deciding, as PR 1.6f's note requires: all 29 are `[operator]`/`[arg-type]` in those four
  files, all from the one documented root cause (the shared indicator-handle dict collapsing to
  `float | MACDValue | SupportResistanceValue`). **Re-keyed, not newly excluded** — deleting the
  lines would have hidden old debt behind a move, and fixing the union inside a move would have
  made the move unreviewable.

### 4.3 And a third, which the gate found and no unit test could

The **sanity tier** failed on the first gate run, and it is the more valuable of
the three findings.

`test_every_strategy_on_disk_is_registered` scans `src/domain/strategies` by
path and compares the count with the real `StrategyRegistry`. The path moved, so
it counted 0 on disk against 7 registered — a loud failure, because the *other*
side of that assertion is read from production. Retargeted, and given the
non-emptiness assertion HLD §9.3 rule 4 asks for: 0 == 0 would have passed the
day the registry was empty too.

Its neighbour was worse and nothing had noticed. `test_every_use_case_resolves_to_a_handler`
scanned `application/use_cases` **alone** — and `EPIC-025` has been moving
contexts out from under that path since PR 0.4a. Measured on the tree that
exposed it: the guard was checking **4** of the application's **26**
`Command`/`Query` classes (4 legacy, 11 `market_data`, 9 `trading`, 2
`strategy`), and its `checked > 0` assertion kept it green for three phases
while it lost 85% of its subject.

Fixed as a seam rather than a list, the way `ui_trees.py` was: `_use_case_roots()`
reads `src/modules/*/application` off disk, so Phase 3's `backtesting` cannot be
forgotten, and `_MINIMUM_USE_CASES_CHECKED = 20` turns a *narrowing* into a
failure — chosen so that seeing only the legacy tree, or only any one module,
fails. Both roots it still names by path are now rows in
`scanned_roots_registry.py`. All 26 resolve, so widening the scan surfaced no
second defect; what it bought is that the next narrowing says so.

### 4.4 What did not move, and why

`register()` binds **nothing**. Like `trading` at PR 1.3a, this module arrives as a move and
`binance_bot_module.py` still holds the container bindings — which costs no boundary violation
because the boundary scan skips that file by name. They come in when there is a port to bind them
behind, which is 2.1c; `register()` may not resolve (SDD §4), so binding first would mean this
module resolving types its consumers still reach for directly.

`contribute()`, `declare_cli()` and `subscribe()` are unimplemented, and each absence is a
measurement written into `module.py`: the strategy cards need `BaseStrategy` from this module and
so could not move before it existed (2.1e); `trade-once` reads as this context's command but which
context owns it is a question about one command rather than a rider on a move (2.1g, and the
allowlist entry for it says so); the Qt feeds travel with the widgets.

### 4.5 Findings outside the step

- **`base_strategy.py:37` — `BaseStrategy` declares 19 public methods**, over
  `architecture-rule.md` §5 rule 4's ceiling of 15. It declared 19 before the move as well
  (verified against `master-warrior`), and that ceiling is an `eye` check rather than a gated one,
  so nothing measured it while the class sat in `src/domain/`. Not fixed here: the 19 are a
  scripting surface rather than a God object — five are the signal verbs
  (`buy`/`sell`/`hold`/`short`/`cover`), four are `input_*` parameter declarations, and splitting
  them inside a move would make the move unreviewable, which is the same argument the mypy re-key
  above rests on. It belongs to whichever pull request next changes that class's shape, and 2.1e is
  the likely one.
- **A near-miss in this pull request's own verification, worth writing down.** The first probe of
  the widened rule — plant a `modules/strategy/domain → support/indicators/ui` import and require
  the guard to refuse it — **passed**, which would have meant the widening was too loose. It had
  not: the edit anchored on `from __future__ import annotations`, a line that file does not contain,
  so the plant never landed and the probe was vacuous. Re-run with the plant verified before the
  assertion, the guard fails and names the exact pair. The lesson is the review skill's §5 read
  literally: running the check is not enough if the *setup* is not also checked, and a probe that
  cannot fail proves as little as a test that cannot.
