# BOT-173 — Readiness can use the exchange's facts: one asynchronous snapshot every venue-dependent check plugs into

**Status:** 🟡 In progress
**Priority:** P2
**Board:** Readiness judged only local state, so no check that needs the venue (leftover base, free balances, open orders) could show before Start or Resume; being built: one exchange snapshot (loading / unavailable / loaded) and pure rules over it.
**Source:** the owner, 2026-10-09 (coordinator session): "Build a mechanism, not a one-off feature. … one seam that every such check plugs into … Each further check is then one more pure rule."
**Risk:** 🟡 — Start and Resume now depend on an exchange read; a wrong rule would wrongly refuse. Mitigated by "loading/unavailable are named, never zero" and by the Start/Resume gates reading afresh, so the click is judged by the same rules on current facts.
**Complexity:** L — new contract, reader, query, rules, a screen loader with fencing, two gates (Start, Resume), SPEC/HLD.
**SPEC:** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** BUG-196 (#455, `ITradingSession.earlier_runs_inventory`)

---

## 1. Context and problem
`assess_readiness` (`readiness_assessment.py`) and the Run step's facts (`bot_run_facts.py`) are built from state this process holds; the screen never asks the exchange before Start. So no check that needs a venue fact can appear before the click. BUG-196 had to show "left from earlier runs" only after Start (its Fix section: "a pre-Start item needs an asynchronous load on selection, a follow-up"). BUG-195 (`-2010` on a Resume's first SELL) is the same gap: the account's *free* base was never compared with what the ladder sells.

Two existing facts shape the design:
- `BotReadinessReader.read` (the Start gate) already reads the account at the click, off the UI thread; only the screen's `detail_for` is local-only.
- `CAPITAL_ABOVE_BALANCE` (`grid_account_checks.py`) already refuses a capital above the Connect step's free quote. Rule 3 below is the same truth at a finer grain, so it **moves** onto the seam (one source of the balance judgement) rather than becoming a second item for one cause.

## 2. Acceptance criteria
- [ ] An `ExchangeSnapshot` has exactly three states — loading, unavailable (with its reason), loaded (immutable facts) — and a rule cannot read a fact from the first two.
- [ ] Selecting a bot at rest (DRAFT/STOPPED) or HALTED loads the snapshot off the UI thread; it is refreshed on demand (Bots → Refresh exchange check) and after every state change of the selected bot; a late answer for another selection or an older request is dropped and logged; shutdown and deselection cancel it.
- [ ] Loading: the Run step shows "Checking the exchange…" and Start/Resume are not enabled; unavailable: the Run step names the reason with Refresh as the fix and Start is not enabled; neither is treated as an empty or zero fact.
- [ ] Rule 1 (earlier runs): before Start, an advisory "A previous run kept X ETH ≈ Y USDT that this run will not trade"; does not block.
- [ ] Rule 2 (resume base): Resume is refused when free base (plus base locked in the bot's own resting SELLs, which Resume cancels first) is below the SELL quantity the resumed ladder needs; the reason names both numbers. Enforced on screen (Resume tooltip) and by `GridResumeSequence.propose` on a fresh read, before the proposal.
- [ ] Rule 3 (start quote): Start is refused when the free quote is below the opening buy plus the BUY ladder; the reason names both and the largest capital that fits. `CAPITAL_ABOVE_BALANCE` leaves the kind's checks.
- [ ] The Start use case judges the same rules on facts read at the click (a snapshot that cannot be read refuses, naming why).
- [ ] Every further check is one more entry in `RULES`; the extension cases are in the rules module's docstring.
- [ ] SPEC-014 and HLD 11 describe the snapshot and the three states.

## 3. Design
**Decision (severity of rule 2).** Refuse, not warn. The first SELL after the BUY would be refused by the exchange for certain (BUG-195's `-2010`) and the run would halt with the BUY already placed; refusing before the proposal costs nothing and names the shortfall. Shrinking the SELL side to the free base instead was rejected: BUG-195 shows the bot's books and the account disagreed, which wants a human, not a quietly smaller ladder. Rule 1 is an advisory: the base may be kept on purpose (BUG-196 owner decision C).

**Layers (architecture-rule).**
- `bots/contracts/exchange_facts.py` — `ExchangeFacts` (frozen: free/locked base and quote, the bot's own resting orders' base/quote, other open orders, earlier-runs base and cost, `can_trade`, `read_at`) and `ExchangeChecking | ExchangeUnavailable | ExchangeLoaded` (the snapshot).
- `bots/application/services/exchange_facts_reader.py` — the one venue read (account holdings via `IVenueAccounts`, open orders via `account_activity`, earlier runs via `ITradingSession`). Never raises: any failure is `ExchangeUnavailable(reason)`. Seam precedent: `planner_numbers._open_orders_on`.
- `bots/application/queries/get_exchange_facts/` — `GetExchangeFactsQuery(bot_id)`.
- `bots/application/services/ladder_needs.py` — pure: what a Start / a Resume needs (quote for opening buy + BUYs, base for SELLs), from the same plan functions the executors use (`resume_plan` is extracted so Resume's sizing has one copy).
- `bots/application/services/exchange_rules.py` — pure rules over `(RuleContext, ExchangeFacts)`; `RULES` is the registry.
- `assess_readiness` gets `exchange` + `purpose`; the exchange items join the Run step; `BotReadiness.advisories` carries the non-blocking ones (the kind's "advice is never an item" rule applies here too).
- Screen: `ReadKind.EXCHANGE` on the presenter's `FencedReads` (action id, newest-wins, stale drop, `drop_all` on shutdown) — no new concurrency machinery; `SelectedBot.exchange` resets to *checking* on every selection so one bot's facts are never judged for another.
- Gates: `BotReadinessReader` (Start) reads the snapshot synchronously and calls the same `assess_readiness`; `GridResumeSequence.propose` reads after cancelling the tagged orders and applies the Resume rules.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/contracts/exchange_facts.py` | `ExchangeFacts` and the three-state `ExchangeSnapshot` (`ExchangeChecking` · `ExchangeUnavailable` · `ExchangeLoaded`) |
| `bots/contracts/bot_readiness.py`, `bot_command_result.py` | `ReadinessAdvisory`, `BotReadiness.advisories`, `ReadinessFix.REFRESH_EXCHANGE`; refusals `EXCHANGE_NOT_READ`, `BALANCE_TOO_SMALL` |
| `bots/application/services/exchange_facts_reader.py` | The one venue read over the trading ports; never raises, never an empty account |
| `bots/application/services/exchange_rules.py` | `RULES` and `judge_exchange`: the three first rules as pure functions; the extension cases in the docstring |
| `bots/application/services/ladder_needs.py`, `domain/grid/grid_needs.py`, `grid_resume_plan.py` | What a Start / a Resume asks of the account; `resume_plan` extracted so the executor and the screen size one ladder |
| `bots/application/services/readiness_assessment.py`, `bot_readiness_reader.py` | The exchange joins the Run step (only once connected and Design is clear); Start reads the snapshot at the click |
| `bots/application/services/resume_readiness.py`, `use_cases/resume_bot/handler.py` | The Resume rules and the Resume use case's refusal, HALTED only |
| `bots/application/queries/get_exchange_facts/` | `GetExchangeFactsQuery` and its handler |
| `bots/domain/grid/grid_constraints.py`, `grid_account_checks.py` | `CAPITAL_ABOVE_BALANCE` leaves the kind's checks (rule 3 replaces it) |
| `bots/ui/bots_screen/exchange_check.py`, `fenced_reads.py`, `selected_bot.py`, `bots_presenter.py` | `ReadKind.EXCHANGE` on the existing fenced reads; `ExchangeCheck` asks on selection, on demand, on a state change and after a command; stale answers dropped, cancelled on deselection and shutdown |
| `bots/ui/bots_screen/bot_detail.py`, `bot_action_rules.py`, `readiness_words.py`, `bot_plan_panel.py`, `fix_next_item.py`, `bots_commands.py`, `bots_command_binding.py`, `bots_view_model.py`, `bots_failures.py` | The Resume tip, advisories under the Run items, Bots → Refresh exchange check and its fix, the Capital field's sentence kept via `field_verdicts` |
| `bots/composition/*` | Bindings of the reader, the Resume reader and the query |
| `trading/contracts/testing/*` | `a_funded_status`, `FakeAccountActivity.open_orders_raise` (verified) |
| `Docs/SPEC/SPEC-014…`, `Docs/HLD/11…`, `Docs/VOCABULARY/README.md` | The snapshot, its three states, the rules; two vocabulary rows |
| `Tasks/bug_report/…BUG-195/196` | BUG-196's follow-up delivered; BUG-195 gains a guard and stays Open |

## 5. Testing
Pure-rule unit tests (each rule × loading/unavailable/loaded × boundaries, mutation-verified); reader unit test over fakes; presenter tests for loading, unavailable, stale-selection fencing, superseded request, cancellation on shutdown and on a bot with nothing to check, refresh on demand and on a state change; Start/Resume gate tests; one integration test on the fake exchange. No test touches a real exchange.

## Implementation notes (written when done)
- **Severity decided (not asked):** rule 2 *refuses* (see §3); rule 1 *advises*; rule 3 *refuses*. Recorded here because the owner asked to be asked only if ambiguous; the alternative (shrink the resume's SELLs to the free base) is the one place the owner may want to override.
- **Rule 3 moved, not added.** The balance already had a Design verdict, `CAPITAL_ABOVE_BALANCE`, built on the Connect step's `AccountView`. A second item for one cause would have been wrong and the finer rule (the plan's exact need, which is below the capital by the empty level's share) could never fire behind it, so the verdict left the kind's checks and the rule replaced it. Cost: the capital is no longer judged until the snapshot is loaded; the Plan says "Checking the exchange…" in that gap. `field_verdicts` keeps the sentence on the Capital field.
- **The snapshot reads through the venue's trading ports** (`account_snapshot`, `account_activity`, `trading_session.earlier_runs_inventory`), not `IVenueAccounts`: no second read of the Connect step's account snapshot (which would have doubled the reads the Connect tests count), and Start and Resume see the same account the orders will be placed against.
- **Exchange items are judged only once Connect is done and Design is clear** (the plan stands): Connect, the Run step's venue item and Design already say what blocks a plan, and the facts would repeat one cause as two.
- **The Start gate reads under `BotCommandLock`**, as it already read the account there; it now also reads open orders and the earlier-runs history, so the lock is held a little longer per Start.
- **Limits, stated:** (1) the screen's Resume judgement sizes the resumed ladder from the bot's own record of its inventory and the market's mid price; the proposal that follows derives the inventory from the exchange again, and a disagreement between the two is the unexplained part of `BUG-195`. (2) The Resume use case judges at the click, before the proposal; a base locked between the proposal and its confirmation is still the exchange's refusal. (3) The facts are not polled: a snapshot older than the user's last look can be stale, and the click is the authority. (4) The fake exchange keeps a resting order's funds free, so the integration test proves the reads and the refusals, and the unit tests prove the locked arithmetic.
- **Verification (revision under test: this branch's head when pushed).** Commit tier (`ci-local.ps1 -SkipTests`: ruff, format, mypy, reference check): PASS. `tests/unit`: 10,499 passed (`test_ci_local_checkout_name_guard.py` needed `pwsh`, installed per `install-rule.md`, 3 passed). `tests/integration`: 490 passed, 1 failed: `test_workbench_conformance[True-1024x700]`, which fails identically on the base (re-run on the stashed base). `tests/sanity`: 42 passed. `tests/unit/architecture`: 708 passed. The `-Full` run is GitHub Actions' on the PR head: **not run locally, not yet observed**. Desktop E2E not run here. Never run against a real exchange.

## Resume
Branch `claude/exchange-readiness-snapshot`. Open: the `-Full` GitHub run on the head, the reviewer's read, and moving this file to `completed/` with `✅ Done` once both are in.
