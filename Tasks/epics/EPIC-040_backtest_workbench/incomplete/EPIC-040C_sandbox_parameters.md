# EPIC-040C — Backtest parameters are a sandbox copy of a bot's plan, judged by the symbol's rules only

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"back test could have another input parameters panel, that will not check the real equity of real account"*
**Risk:** 🟡 — the boundary between a simulation and a real bot; a leak either way is a real-money defect
**Complexity:** M — a small model, the kind's existing editor reused, one wording path
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040A](../completed/EPIC-040A_pin_grid_backtest_behaviour.md)

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
| `src/modules/bots/ui/backtest/sandbox_plan.py` | New value object |
| `src/modules/bots/ui/backtest/sandbox_verdict_words.py` | The workbench words an account check that did not run as "not checked in a simulation". This is a presentation choice; the domain constraints are untouched |
| `tests/unit/modules/bots/ui/backtest/test_sandbox_plan.py` | Copy, diff, reset, reselect |
| `tests/unit/architecture/test_sandbox_sends_no_command.py` | Guard |

## 5. Testing
- Unit tests for the value object and the wording.
- An integration test on the fake exchange: edit, run and reset, then assert no command and no order-session request.
- The architecture guard.
