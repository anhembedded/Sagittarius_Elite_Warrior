# EPIC-025C — Phase 2: `modules/strategy` (the Core domain)

- **Status:** 🟡 In progress since 2026-09-16 — **2.1a, 2.1b, 2.1c and 2.1d done**: the
  unblocking measurement (§3.3), the move itself (§4), `IArmedStrategy` with the catalog measured
  out (§5), and `ISizingPolicy` with `MarginRiskPolicy` split (§6). Allowlist 23 → 42 → 40 → 36.
  Next: **2.1e**, the UI. §3.4 carries the remaining cut, measured rather than estimated.
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
| ~~2.1c~~ ✅ | **`IArmedStrategy` published** — `ArmedStrategySnapshot`, both Presenters off `LiveStrategySession`. `IStrategyCatalog` was written, measured against its four would-be consumers, and **deleted**: see §5 | **42 → 40** |
| ~~2.1d~~ ✅ | **`ISizingPolicy` published** (ADR D17) — `position_sizing_bridge` moved in, `MarginRiskPolicy` was **split** and only its sizing method came, `PositionSizing` went to `core/vo`, and `trading`'s published surface gained `OrderQuantityRoundingPolicy`. The `trading → backtesting` pair this whole allowlist was written to catch is gone: see §6 | **40 → 36** |
| 2.1e | the UI: `strategy_arming_coordinator`, `signal_feed`, `strategy_display`, `strategy_params`, `strategy_overlay` → `modules/strategy/ui/`, with the strategy card contributed to both surfaces (§1 item 4) | shrinks |
| 2.1f | `ITradingSession.claim_symbol`/`release_symbol` — the lease `IOrderSubmission` shipped without, whose first consumer is `arm_strategy` (`Docs/SDD/05` §3) | unchanged |

`2.1e` inherited one line from 2.1d: PR 2.1d found that `ISizingPolicy` does **not** pass through
`LiveStrategyFactory`'s arguments, so the container-binding move that `module.py` and
`composition/port_bindings.py` had both scheduled for 2.1d travels with `2.1e` instead, where the
strategy card and the chart overlay give it a reason. Both docstrings now say so rather than
keeping the prediction.

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

---

## 5. PR 2.1c — one port shipped, one measured and deleted

### 5.1 What shipped: `IArmedStrategy`

`contracts/i_armed_strategy.py` + `contracts/armed_strategy_snapshot.py`, implemented by
`LiveStrategySession`, bound in `StrategyModule.register()` through
`composition/port_bindings.py`. Two allowlist entries retired: both live Presenters stopped naming
the session.

The DTO's shape is a measurement, not §1 item 2's sentence. That said *"`ArmedStrategySnapshot`
(carrying `symbol`)"*, and `LiveStrategyConfig` **already carries `symbol`** — so a snapshot of
those fields would have been field-for-field identical, which is the `PositionSnapshot` outcome
`Docs/SDD/05` already records. What the consumer needed was different:

```python
armed_config = self._strategy_session.config      # one acquisition of the session lock
strategy_owns_symbol = (
    self._strategy_session.is_armed               # ...and a second
    and armed_config is not None
    and armed_config.symbol == symbol
)
```

Two facts that are **not** the same fact — the value the user armed, and whether an engine was
built from it — read through two acquisitions, so a strategy armed between them was observable as a
config with no engine. `armed()` answers both under one acquisition and the snapshot carries
`config` and `engine_running`. That is the one behaviour this pull request changes, in the safe
direction, and `Docs/SDD/05` §2c records it as a deviation from the spec's own field list.

Proof the wiring is real, not assumed: removing `container.singleton(IArmedStrategy, …)` turns
`tests/sanity/test_composition_root.py::test_every_navigable_route_constructs` red for **both**
`dashboard` and `trading`. Probed, not reasoned about — and it means no new test was needed for
the binding, which is what `testing-rule.md` §1 wants of this tier.

### 5.2 What did not ship, and why deleting it was the step

`IStrategyCatalog` is in HLD §3.4 and this pull request **built** it: the ABC, `FakeStrategyCatalog`,
a four-guarantee contract suite, `StrategyRegistry` implementing it, and `trade_once_cmd` and
`backtest_presenter` moved onto it. Then the four would-be consumers were read properly, and every
one of them needs the strategy **classes**:

| Caller | What it does with `available()` |
| :--- | :--- |
| `trading_presenter`, `dashboard_presenter` | hand it to `StrategyArmingCoordinator` and `StrategyOverlayCoordinator`, which call `.get(key)` and construct the strategy for `chart_line_colors()` / `chart_line_widths()` |
| `backtest_presenter` | hands it to `StrategyConfigCoordinator` and `IndicatorCoordinator`, which do the same |
| `trade_once_cmd` | hands the registry itself to `build_engine()` |

A port answering with keys retires **none** of those, and a published contract may not carry
`BaseStrategy`. Widening `IStrategy` — which declares `evaluate()` and nothing else — would publish
chart concerns to every strategy that implements it.

So the port was deleted rather than shipped with nothing to serve. The alternative, keeping it for
the two key-reads while those files still resolve the concrete registry for their coordinators, is
half a migration: two ways to ask one question in one file, no entry retired, and every consumer's
test carrying a binding for a port nobody calls. `Docs/SDD/05` §2b records it beside
`ITradingSession.claim_symbol` and PR 1.2's `list_symbols(quote_asset)` — the same lesson twice
before.

It is worth writing at **2.1e**, when the three UI callers' class-reads become intra-module; the
CLI's exits with `IStrategyEngineFactory` in Phase 3. The allowlist's own block says so per entry.

### 5.3 The gate found a tier the selective runs could not

First gate run **failed**: four integration tests, all of them containers that bind
`LiveStrategySession` by hand and now had to answer `IArmedStrategy` too. The unit-tier containers
had been fixed while the port was being written — the integration ones were not, and no selective
run touched them, so only the full gate said so. One of the four also reached into
`presenter._strategy_session` directly, an attribute this pull request renamed because its *type*
changed.

Worth naming rather than just fixing: **seven** hand-written containers in this repository answer
`resolve()` with an `if interface == …` chain or a dict, and each one is a place a new port has to
be remembered. That is not this step's to fix, but it is why publishing a port costs more than the
port — and it is the concrete argument for the fake-and-contract convention, since a consumer test
that took `FakeArmedStrategy` from `contracts/testing/` would have needed no edit at all.

### 5.4 What the review caught

Run before merge, and it found two of the same kind — a document naming a type, where the type had
moved out from under the sentence:

- `Docs/VOCABULARY`'s **Strategy** row said strategies are *"Listed by `IStrategyCatalog`"*. After
  §5.2 that port does not exist, so the row named nothing. Corrected to name `StrategyRegistry`
  with the measurement and the port's planned status.
- **`ArmedStrategySnapshot` had no vocabulary row at all.** It is a published type and "what is
  armed" is a term this app uses on three screens, which is exactly `pr-review` K5's question. Added,
  with the two-fields-because-two-facts reason, so the next reader does not have to infer it from
  the dataclass.

Nothing was found against the code. The E12-style probe of the new binding is in §5.1.

### 5.5 Findings outside the step

- `backtest_presenter`'s picker read and `trade_once_cmd`'s key check are *contract* reads sitting
  in files that also need the concrete registry for another reason. Nothing is wrong with them
  today; they are the two call sites that make `IStrategyCatalog` worth having once 2.1e removes
  the other reason, and they are named here so that pull request does not have to re-find them.

---

## 6. PR 2.1d — `ISizingPolicy`, and the two things the decision got slightly wrong

Allowlist **40 → 36**: six entries retired, two arrived, and one of the six is the pair this file's
header says the whole ratchet was written to catch — `trading → backtesting`, a dependency HLD §2.1
forbids and no diagram in this repository ever drew.

| Retired | Why |
| :--- | :--- |
| `trading.…position_sizing_bridge → backtesting.…margin_risk_policy` | the sizing rule is `strategy`'s now (§6.2) |
| `trading.…position_sizing_bridge → domain.value_objects.position_sizing` | `PositionSizing` is `core/vo` (§6.1) |
| `strategy.…live_trading_coordinator → domain.value_objects.position_sizing` | the same |
| `strategy.…live_trading_coordinator → trading.…position_sizing_bridge` | the bridge is intra-module |
| `cli.order_preview_formatter → trading.…order_quantity_rounding_policy` | published (§6.3) |
| `cli.trade_once_cmd → trading.…position_sizing_bridge` | replaced by the same import one prefix over, which PR 2.1g retires with the command |

| Arrived | Repaid by |
| :--- | :--- |
| `cli.trade_once_cmd → strategy.…position_sizing_bridge` | PR 2.1g — `trade-once` becomes strategy's declared CLI command |
| `backtesting.paper_exchange → strategy.…margin_sizing_policy` | `EPIC-025D` — `modules/backtesting` resolves `ISizingPolicy` from the container instead of defaulting it |

The second arrival is worth reading carefully, because the *dependency* it records is legal and only
the **default** is not. `PaperExchange`'s constructor takes `ISizingPolicy` — a contract, which a
legacy file may import freely and which needs no entry. What the entry records is the `or
MarginSizingPolicy()` fallback: sixty construction sites in this repository pass no policy at all,
so something has to name the implementation to build when nobody hands one over. That is the shape
PR 0.5 and PR 1.3b ran twice, and it is the shape
[`EPIC-025D`](EPIC-025D_phase3_backtesting.md) already scheduled — *"`backtesting` sizes paper fills
through `strategy.contracts.ISizingPolicy` (ADR D17), so backtest and live sizes are one number by
construction"*.

### 6.1 `PositionSizing` moved with no argument needed

HLD §2.4's table had already decided it — *"✅ (the value type stays neutral; the rule that uses it
belongs to `strategy`)"* — and reading the file confirmed the row: a frozen dataclass, a `str` enum
of four members, range validation, and no trading rule anywhere. So it moved to
`core/vo/position_sizing.py` as a move plus an import rewrite, which is what §2.4's own admission
rule promises such a promotion will be. Its measured consumer list is in fact wider than 2026-09-11
recorded: the backtest UI, both backtest commands, `config_keys`' comments and `trade_once_cmd` name
it too.

### 6.2 The finding: `MarginRiskPolicy` was two rules, and moving both would have re-drawn the arrow

ADR D17 says *"`MarginRiskPolicy` and `position_sizing_bridge` move from `domain/backtesting` and
`domain/trading` into `modules/strategy/domain/`"*. Measured against the class, that is one method
too many. `MarginRiskPolicy` declares four:

| Method | What it is | Whose |
| :--- | :--- | :--- |
| `calculate_margin_and_notional()` | how much capital an entry may use | **sizing — `strategy`** (ADR D17) |
| `get_leverage()` | which configured leverage applies to a direction | a paper broker's books |
| `mark_to_market()` | what an open position is worth right now | the same |
| `calculate_realized_pnl()` | PnL, PnL %, and balance release on close | the same |

Its logger is even named `App.PaperExchange`. Moving the whole class would have put PnL realization
inside `modules/strategy`, and then Phase 3 — which turns `backtesting` into a module — would have
had to import `calculate_realized_pnl` from `modules/strategy/domain/`, a module-to-module
non-contract import: the same wrong-direction arrow this pull request exists to delete, one context
over and one phase later.

So the sizing method left as `MarginSizingPolicy`, the other three stayed where they are, and the
formula is the one `BOT-104` and `BOT-041` wrote, unchanged. **This is the fourth time in this epic
that one file has been found holding two things with different owners** — PR 2.1a's
`order_intent.py`, PR 2.1b's indicator surface, PR 2.1c's catalog, and now this one — which is
enough of a pattern to expect it at 2.1e rather than be surprised by it.

The port's shape is the second correction. ADR D17 says `ISizingPolicy` *"computes the order
quantity"*; it cannot, because a quantity is capital divided by a price and then rounded down to the
symbol's lot filter, and the same ADR leaves the exchange's filters with `trading`. `allocate()`
therefore answers a named `MarginAllocation` — the margin an order locks and the notional it buys —
and the capital-to-quantity step is `position_sizing_bridge`, `strategy`'s own domain code, which
nothing outside the module needs to know about. ADR D17's line is exactly the line that shipped;
what moved is which side of it the published method sits on. `Docs/SDD/05` §2d records both
corrections.

Two smaller choices, so a reviewer does not have to re-derive them. **The bridge constructs
`MarginSizingPolicy` directly** rather than taking `ISizingPolicy` as a parameter: a port is how a
consumer across the boundary asks, and the bridge is this module's own domain code sitting beside
the implementation — it constructed `MarginRiskPolicy()` the same way before the move, and adding
an injection point nothing else needs is the seam `architecture-rule.md` §7.2.1 says to cut at the
second consumer. **The bridge's `if not allocation.is_fundable` guard is unreachable with today's
implementation** — `MarginSizingPolicy` answers `NO_ALLOCATION`, whose zero notional divides to
zero anyway — and it stays because what it actually refuses is a *negative* notional turning into a
negative order quantity, which is a second implementation's failure mode rather than this one's.
That is written at the guard rather than left for a reader to test.

### 6.3 `OrderQuantityRoundingPolicy` is published, on PR 2.1a's own argument

The bridge rounds, so once it is `strategy`'s it has to reach trading's rounding rule — and copying
`ROUND_FLOOR` into a second file is the drift disease `CLAUDE.md` records this repository catching
twice. Measured before deciding, exactly as PR 2.1a measured `OrderIntent`:

- `contracts/order_preview.py` — a **published DTO** — has a `notional_check: NotionalCheck` field,
  so any consumer reading that answer had to import the enum out of the module's `domain/`. The
  type already crossed the boundary; the file just had not moved with it.
- Two callers outside the module name the policy itself (`cli/order_preview_formatter.py`,
  `scripts/epic021c_metadata_probe.py`), which is HLD §2.4's admission rule.
- It carries no trading decision. What the venue accepts is a filter; whether to trade at all is
  `TradingLimitPolicy`, which stays in `domain/policies/` where nothing outside may reach it.

### 6.4 Why the bridge still rounds, although ADR D17 says `trading` rounds

It rounds twice today: `position_sizing_bridge` rounds down to `step_size`, and the submit path's
`PreviewOrderQueryHandler` rounds the result down again, against the same `step_size` from the same
`IMarketMetadataProvider`. Removing the first looks like exactly what ADR D17 asks for, and the
measurement says not to:

rounding down twice is idempotent, so the *quantity* is identical either way — but a sub-lot
quantity is only **zero** after rounding. With the bridge's rounding, `LiveTradingCoordinator`
answers *"Computed live order quantity was zero for balance X at Y% sizing — nothing to send"* and
publishes it to the Trading screen's log panel. Without it, the quantity travels on, `preview`
rounds it to zero, and the operator is told `MIN_NOTIONAL` instead. That would be undoing
`BUG-084`'s own fix, which is the commit that made this distinction visible in the first place — so
the rounding stayed, and the bridge's docstring says why.

### 6.5 No verified fake, and that is against HLD §10.3 rule 1 on purpose

Every other published port in this module and in `trading` ships one, because every other port
reaches something a test cannot have. This one is arithmetic: pure, in-memory, instant, no I/O to
stand in for. A double could only re-type the formula, or answer canned numbers — which is
[`CS-001`](../../../Docs/CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md), a double that
could not disagree with the code it was standing in for. A consumer that needs a different
allocation gives the real policy different inputs.

So `SizingPolicyContract` runs against the real implementation, in the unit tier, and its reason for
existing is the one ADR D17 gave the user: *"changing how size is computed (ATR-based, Kelly, …) is
one change in the strategy module, and backtest and live change together"*. A second implementation
is what that suite is for. A fake arrives with the first consumer that needs an allocation the
formula cannot produce — `base_feed.py`'s promote-on-the-second-need rule, the same one `BUG-126`
applied when it deleted a feed instead of keeping it.

### 6.6 Tests

Moved, not rewritten (ADR D18): the four `position_sizing_bridge` cases to
`tests/unit/modules/strategy/domain/policies/`, and the five sizing cases out of
`tests/unit/domain/backtesting/policies/test_margin_risk_policy.py` into
`test_margin_sizing_policy.py` beside them — numbers and comments unchanged, the only edit being
that the answer is a named `MarginAllocation` rather than a bare pair. That file keeps its other
five cases and says at the top where the missing ones went, so a reader counting tests is not left
to wonder. `test_order_quantity_rounding_policy.py` moved from `tests/unit/domain/policies/` —
where it had been left behind by PR 1.3a — to `tests/unit/modules/trading/contracts/`, beside its
subject at last. New: `SizingPolicyContract` and the one file that runs it.
