# EPIC-040C — Backtest parameters are a sandbox copy of a bot's plan, judged by the symbol's rules only

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-14: *"back test could have another input parameters panel, that will not check the real equity of real account"*
**Risk:** 🟡 — the boundary between a simulation and a real bot; a leak either way is a real-money defect
**Complexity:** M — a small model, the kind's existing editor reused, one wording path
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040A](EPIC-040A_pin_grid_backtest_behaviour.md)

---

## 1. Context and problem
- Today the backtest reads `selected.edited or bot.config` (`ui/bots_screen/kind_backtests.py:100`). It replays whatever is typed in the live bot's Plan panel, so trying a "what if" means editing the real bot's plan.
- The owner wants a separate parameter set that does not check the real account.
- `BotKindInputs.account` is already optional (`domain/bot_kind_inputs.py`): with `None`, "the constraints that need it then say they did not run". The judgement needs no new mode, only an honest word.

## 2. Acceptance criteria
- [ ] A `SandboxPlan` value holds:
  - the kind id, venue and symbol;
  - the sandbox config;
  - the config it was copied from;
  - the source bot id.

  It answers `changed_fields()`, the keys whose values differ from the source.
- [ ] It is created from a bot's **saved** plan, not the live panel's unsaved edits. Edits change only the sandbox. **Reset** restores the source.
- [ ] Selecting another bot re-copies from that bot's plan, unless the user has edited the sandbox. In that case the workbench asks before discarding.
- [ ] The sandbox is judged by the kind's own `IBotKind.validate` with `account=None`:
  - Symbol rules (tick, step, minimum notional, fees) and the venue's exposure limits still refuse a bad plan.
  - The verdicts that need the account read **"not checked in a simulation"**, not "did not run". The workbench words it; the domain verdict is unchanged.
- [ ] A test proves that no sandbox edit, run or reset ever dispatches a command that writes a bot, opens an order session or reads the account balance.

## 3. Design
**A value object plus the kind's own editor, not a second editor.**
- The sandbox config is edited in a second instance of the kind's `BotKindPanel` (`ui/kinds/bot_kind_panel.py`, already per kind, already reports `config_changed`), set editable.
- A new kind gets a sandbox editor for free.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Second `BotKindPanel` instance + `SandboxPlan` (chosen) | Zero per-kind UI work. The diff is generic (two mappings). P7. |
| A dedicated backtest form per kind | Rejected: it duplicates every kind's editor, which is exactly what the owner asked to avoid. |
| Keep reading the live panel's edits | Rejected: it ties the simulation to the real bot, which is the problem. |
| A "simulation" flag on `BotKindInputs` | Not needed: `account=None` already expresses it. A flag would be a second way to say the same thing. |

**Real-money boundary.** The sandbox lives in the UI layer and talks only to the backtester port (040B) and read-only queries (terms, candles, brackets). Enforcement:
- no dispatcher command type is reachable from the sandbox package;
- a guard lists the commands it may send: none, queries only.

**Risks:**
- **Copying from unsaved edits by accident.** Mitigation: a test that edits the live plan without saving and asserts the sandbox shows the saved values.
- **Editor side effects.** Some `BotKindPanel` behaviour may assume it edits a real bot, such as the planner-market suggestions. Read `grid_panel.py` before reuse and note any coupling.

## 3a. Reuse
- **Editor:** used `BotKindPanel` and `kind_panels.panel_for(kind_id)`.
- **Judgement:** used `IBotKind.validate` and `BotKindInputs(account=None)`.
- **Market reads:** used the `GetPlannerMarketQuery` terms read.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/backtest/sandbox_plan.py` | New: `SandboxPlan` (frozen; `from_bot`, `changed_fields`, `with_config`, `reset`) |
| `src/modules/bots/ui/backtest/sandbox_session.py` | New: which sandbox the tab holds as the selection moves; asks once before discarding edits and remembers a declined copy (pure logic, no widget) |
| `src/modules/bots/ui/backtest/sandbox_judge.py` | New: `judge_sandbox` (the kind's `validate` with no account) and `sandbox_line` ("Not checked in a simulation") |
| `tests/unit/architecture/test_sandbox_sends_no_command.py` | New guard, an allow-list: the sandbox may import only the nine project modules it names (values, the kind's `validate`, the planner's read-only terms), so no command, dispatcher, store, runner, order port or account read can enter unseen |
| `tests/unit/modules/bots/domain/backtest/test_sandbox_plan.py`, `tests/unit/modules/bots/ui/backtest/` | Copy, diff, reset, reselect, judging and wording |
| `tests/integration/modules/bots/test_a_sandbox_run_touches_no_bot_order_or_account_on_the_real_module.py` | The real module's graph, each registered singleton watched |
| `Docs/MODULES/bots/`, `Docs/VOCABULARY/README.md` | `08-concepts.md`, `README.md`; a vocabulary row |

## 5. Testing
Unit tests for the value object, the session rule and the wording; the guard and its probe; an integration test on the real module (copy, edit, judge, run through the catalog's real backtester, reset; the dispatcher, the account reads, the venue's trading ports and the bot store each watched, and each watch proven able to fire).

## Re-check against master (2026-10-20, `6c5f05a`)
The design held. What changed since 2026-10-14, and the re-scopes:
- **Where the value lives.** `SandboxPlan` has no widget and no UI dependency, so it sits in `domain/backtest/` beside the outcome (kind-neutral, importing no kind: the `EPIC-040B` guard covers it). The session rule and the wording are UI-layer logic in `ui/backtest/`, as the task said.
- **No second `BotKindPanel` yet.** The acceptance criteria do not need one and nothing can host it until `040D`'s workbench exists. What it must handle is recorded in `040D` (below).
- **`EPIC-039`'s venue limits and risk facts** are part of judging: `judge_sandbox` passes the venue's `ExposureLimits` (for the kind's markets) and the symbol's `PlanRiskFacts`, so a Futures sandbox is refused a direction or a leverage the venue does not allow, as the bot's own plan is.
- **The judgement seam already existed.** `bot_plan_judge.judge` takes a `PlanWorld`; the sandbox is `PlanWorld(account=None)`. No new mode, no flag on `BotKindInputs`.
- **"Not checked in a simulation".** Two verdicts are about the real account and answer "OK, did not run" without it: `KEY_NOT_READ` and `FOREIGN_ORDERS_NOT_READ`. `sandbox_line` words both; the domain verdicts are unchanged. The balance is not a verdict of `validate` (it is the readiness's `quote_short_for_ladder`), so a sandbox has no balance check to word.
- **The orders already open on the symbol** are a fact of the real account that the planner's market read carries (`foreign_open_orders`). The sandbox sets it to `None` before judging, so it is not judged against them.

## Implementation notes
**What shipped.** The frozen `SandboxPlan`; `SandboxSession`, whose `follow(bot)` copies a bot's **saved** plan, treats the same saved plan arriving again as no change, treats a changed saved plan, another bot, or the same bot on another venue as a new source, and, when the sandbox has edits, answers `NEEDS_CONFIRMATION` once and keeps the edits until `confirm_switch` or `keep_current` (a declined copy is remembered, so the screen's next refresh does not ask again); `judge_sandbox` and `sandbox_line`; the guard; the tests. No product screen shows a sandbox yet (`040D`), and no behaviour of the Bots screen changed.

**Real-money boundary, proved two ways.** By construction: the guard is an allow-list, so a new import of a project module fails until it is named (a first draft was a deny-list that missed `from package import port` and a second alias on an `import` line). By execution: the integration test runs the whole flow on the real module's graph with the registered dispatcher, account reads, trading ports and bot store each replaced by a recorder that raises, and a second test calls each one to show the watch fires. The planner market read, which does touch the account's open orders and fee tier, is not on that path: the test hands the judge a built market.

**Review, round 1 (PR #628).** The review found the session asking again on every refresh after "keep", a bot moved to another venue treated as the same source, a guard that was a deny-list with holes, and the Futures limits, the risk facts and the return-to-source branch untested. All fixed: the session remembers what it asked and declined; the source is `(kind, venue, symbol, bot, saved plan)`; the guard is an allow-list; each branch has a test that fails without it. A position venue with no risk facts now says `LIQUIDATION_FACTS_NOT_READ` (the sandbox's own OK verdict) instead of dropping its liquidation checks in silence; `040D` still passes the risk facts. Fees are the account's tier and the docs now say so.

**Mutation checks (each went red, then restored).** Reset keeping the edits (3 tests); a parameter added or removed not counted as changed; an edited sandbox discarded silently (2); the same source re-copying and losing edits; the account no longer withheld (6); the open orders still judged; an account verdict worded as the planner words it (2); after the review, the venue's limits dropped for Spot's, the risk facts dropped, the not-read liquidation verdict removed or made to fire on Spot, a declined copy not remembered, the pending copy not cleared on return to the source, the venue ignored in the source, the open question asked again.

**Findings for `040D`, not fixed here.**
- **The kind panel's commands.** `BotKindPanel.kind_actions()` are the Bots menu's commands (`kind_command_binding.py`), bound to the *selected bot's* panel. A second panel instance for the sandbox must not be bound to them, or a menu command would act on the sandbox's editor while looking like it acts on the bot's. Its `set_plan_facts(account, risk)` takes `account=None`; its `set_planner_market` suggestions are read-only.
- **The planner market read touches the account.** `read_planner_numbers` reads the symbol's terms, and with them the account's fee tier and the open orders on the symbol (`account_activity`). Neither is the balance, and the live panel already makes the same read, so the sandbox reuses `selected.market`. A terms-only read would narrow it; that is a choice for `040D`.
- **Fees are the account's rates.** `ExchangeTerms.maker_fee` and `taker_fee` are the account's fee tier, which a live run would charge. The sandbox keeps them (the task says fees still apply) and the workbench should say whose they are.
- **Position venues.** `PlanRiskFacts` carries the account's current leverage setting for the symbol, read once for the live plan; the sandbox's own plan carries its leverage, and the liquidation estimate uses the brackets. `040D` decides whether the sandbox shows the estimate.

**Verified / not.** Commit tier, the architecture suite and the bots unit tests green. Not verified: nothing shows a sandbox on screen, so no screen or Windows look.
