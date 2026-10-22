# ADR — A Grid's optional trigger price gates its entry like a limit order, inside the same `AWAITING_RANGE` wait

**Epic:** [EPIC-046](README.md)
**Date:** 2026-10-22
**Status:** Proposed (the rule is the owner's; D1–D6 are the author's proposed defaults, which the owner may veto)
**Decided by:** the owner for the rule, 2026-10-22, through the coordinating session: *"cái phần giá kích hoạt làm chưa ta? tui muốn kích hoạt giống limit, giá tốt hơn giá đó mới kích hoạt grid"* (translated: "Has the trigger price been built? I want it to activate like a limit order: the grid activates only when the price is better than that price."). D1–D6: Pending (the reviewer's read, the coordinator's acceptance, the owner's veto)
**Supersedes / superseded by (optional):** extends [ADR 044](../EPIC-044_grid_waits_for_the_range/DECISION_2026-10-21_a_grid_waits_for_the_range.md) D1, D4 and D5 (the wait, the entry rule, the flat Resume); supersedes nothing.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code tree at `f850b18` (`master-warrior`, 2026-10-22); a point-in-time record, so cited as `file:line` at that commit |
| 🟢 User decision | decided by the owner, relayed by the coordinating session |
| 🔵 Proposed | the author's proposal; accepted by the reviewer's read and the coordinator, or vetoed by the owner |
| ❓ Open | blocks the named phase until answered |

## 1. Context

The owner wants a Grid to wait for a price, as a limit order does, before it lays anything. `EPIC-044` already built the wait for the range; nothing holds a bot back inside its range.

**Established facts** (`f850b18`):

- ✅ `GridParams` (`src/modules/bots/domain/grid/grid_params.py:127`) has no trigger field; every key a Grid reads is in `GRID_PARAMETER_KEYS` (`grid_parameter_check.py:17`), which `bot edit` accepts and `bot show --params` lists. A plan file and `bot add` carry a bot's parameters as the same string map (`BotDefinition.config`), so a key `GridParams` reads travels through them with no code of their own.
- ✅ The wait is one gate asked in three places, each by `range_position(...) is RangePosition.INSIDE`: the start (`GridRangeEntry.waits_for_the_range`, `grid_range_entry.py:116`), the waiting bot's price watch and its fresh-book confirmation (`on_price`, `_attempt`, `grid_range_entry.py:135-172`), and the flat Resume (`GridResumeSequence._outside_range`, `grid_resume_sequence.py:221`).
- ✅ Only `AWAITING_RANGE` asks the entry (`on_price` returns at once in any other state, `grid_range_entry.py:138`); `RUNNING` restored after a restart goes `RECOVERING` → `reconcile_ok` → `RUNNING` (`bot_lifecycle_fsm_matrix.py`, `RECOVERABLE_STATES`) and never passes the start sequence's gate again.
- ✅ The Plan and the Start checks judge the ladder at the price the bot will enter at, one place: `entry_plan` (`grid_evaluation.py:117`) clamps the price into the range (ADR 044 D6); the range verdict is `check_price_against_range` (`grid_range_checks.py:36`).
- ✅ The backtest's wait is `WaitingReplay` (`waiting_replay.py`), which enters at the first step whose close is inside the range by the same `range_position`.

**Forces.** The trigger decides when a position opens with real money, so a wrong side means buying above the owner's limit or shorting below it. It must not fork the `EPIC-044` mechanism (17 consumers of the lifecycle, a guard over every hand-written state set), must survive a restart without re-arming a bot that already traded, and must be the same in the backtest.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D0 | **The rule.** A Grid may carry an optional trigger price; it activates only when the price is better than the trigger, like a limit order. | 🟢 Accepted | Owner | The rest of this table says what "better", "price" and "activates" mean. |
| D1 | **What "better" means.** LONG: the entry price **≤ trigger** (a lower buy). SHORT: the entry price **≥ trigger** (a higher sell). The trigger itself counts as met, as a limit order fills at its price. NEUTRAL: refused in words ("a trigger price needs a LONG or SHORT grid: a NEUTRAL grid has no better side to wait for"); see O1. Spot is LONG, so a Spot Grid takes a trigger. | 🔵 Proposed | Pending | One comparison per side, in one function (`grid_entry_gate.py` → `trigger_met`). Example, range 100–140, trigger 125: a LONG started at 135 waits and lays at 124; a SHORT started at 115 waits and lays at 126. |
| D2 | **The price source and the state.** The trigger is judged on the price the range is judged on, by the same path: the mark on Futures, the last trade on Spot, confirmed by the fresh book before any transition (ADR 044 D4). The range is judged first and always: a price outside it never enters, even when it is better than the trigger. The trigger is an **extra condition on the same `AWAITING_RANGE` wait**: no new state, no new event, no new row; `price_outside_range` now also leads in when the price is inside the range but short of the trigger. One gate, `entry_gate(params, price)` → `OPEN` / `OUTSIDE_RANGE` / `TRIGGER_NOT_MET`, replaces the three `range_position` asks of §1. **The state keeps its name** (`AWAITING_RANGE`, persisted in every saved bot record and read by the state-set guard): a rename is a migration of stored records and of 17 consumers for a word, and the words a person reads (the badge, the banner, `bot show`) can name the trigger without it. | 🔵 Proposed | Pending | No lifecycle change, so `test_every_state_set_classifies_every_state.py` and the generated state tables stand. The cost: the code name says "range" for a wait that may be on the trigger; the vocabulary entry and the state-machine page say so. |
| D3 | **Latching.** Once the gate opens and the ladder is laid, the bot is a started grid: it never waits again when the price moves back across the trigger, as a filled limit order does not unfill. The latch is the lifecycle: only `AWAITING_RANGE` asks the gate, and a restart of a running bot returns it to `RUNNING` through `RECOVERING`. A **new Start** (from DRAFT or STOPPED) is a new order and asks the trigger again. A **Resume of a bot that holds nothing** asks it too: like ADR 044 D5's flat Resume outside the range, it is a fresh entry, and the trigger is the owner's limit on any entry; a Resume of a bot that holds inventory or a position is unchanged (`resume_plan`). | 🔵 Proposed | Pending | No persisted "triggered" flag is needed. The flat-Resume choice is the conservative one for real money: without it, a bot that halted before it ever triggered (an `entry_refused`, a `switch_off` while waiting) would be resumed at a price the owner's limit forbids. |
| D4 | **Validation.** A trigger outside `[lower, upper]` is refused at Design in words ("the trigger price 150 must be inside the range 100-140"), by `GridParams` itself, so the Plan editor, `bot edit`, a plan file and `bot add` refuse it by the same rule; `bot edit` judges a changed range, direction or trigger against the others (`grid_parameter_problem`). A trigger already met at Start activates at once, exactly as a start without one. `trigger_price=off`, a blank or no key means none; a definition without one keeps its bytes (the key is written only when set). | 🔵 Proposed | Pending | The bounds are allowed (a trigger on the lower bound of a LONG means "only at the bottom"). |
| D5 | **Surfaces.** The Start check says `TRIGGER_NOT_MET`, information and never a warning: "Starts waiting for the price at or below the trigger X (now Y); nothing is placed until it is"; the Plan and the checks judge the ladder at the trigger, where the bot will enter (`entry_price`, the same one place as ADR 044 D6). The plan file, `bot add`, `bot edit` and `bot show --params` carry the key with no code of their own (§1). **Slice B:** the Plan editor field (optional, empty = off); the waiting status "Waiting for the price ≤ X (now Y)" on the banner, `bot list` and `bot show`; the Discord entry alert names the trigger; the backtest enters by the same gate (`WaitingReplay` asks `entry_gate`), with a replay/live same-step parity test. | 🔵 Proposed | Pending | Slice A makes the rule and the words of the Start check true; slice B makes every place that shows a waiting bot say what it waits for. |
| D6 | **Log lines.** The existing tags, no new one: `[range-wait]` names the cause ("price 135 has not reached the trigger, which wants it at or below 125"), `[range-entry-deferred]` names a fresh book price that the gate refuses. | 🔵 Proposed | Pending | `render_log_templates.py --write` follows. |

## 2a. Constitution check
The rule is the owner's and touches real money (when a position opens), so D1–D6 are not settled as defaults: they wait for the coordinator's acceptance after the review and stand open to the owner's veto. The check is recorded for the reviewer.

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | The gate is one function every caller asks; the mutation of each comparison is red in `test_grid_entry_gate.py` and `test_a_grid_with_a_trigger_waits_for_a_better_price.py` |
| P2 Verify, don't restate | ✅ | §1 cites the code at `f850b18`; the docs link this record rather than restate it |
| P3 A copy drifts | ✅ | No second copy of the rule: the start, the watch, the confirmation, the Resume, the Plan's entry price and the Start check all call `grid_entry_gate.py` |
| P4 Green proves only what was tested | ✅ | The application tests drive the real executor over the simulated venue on Spot and Futures, LONG and SHORT; the backtest is not claimed until slice B's parity test |
| P5 Apply before you invent | ✅ | Reuses the `EPIC-044` state, rows, confirmation and pre-checks; the limit-order semantics are the exchange's own |
| P6 Fix the mechanism | ✅ | The three `range_position` asks became one gate instead of three `and trigger_met` additions |
| P7 Seam now, variant later | ✅ | `EntryGate` names why the gate is closed, so a later condition (a NEUTRAL meaning, a dwell) is one more member |
| P8 Ratchets only fall | ✅ | No test weakened; `test_every_declared_key_is_one_a_grid_reads` gains the key |
| P9 Decide alone | ✅ | Every default is marked Proposed with the owner's veto; O1 is asked, not decided |
| P10 Pyramid and units | ✅ | The examples state the range, the trigger and the prices in quote units |
| P11 Prompt-grade artifacts | ✅ | This record, the SPEC and the state-machine page say the same rule once and link here |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ❌ real money | No dependency, setting, Engine file or secret; a saved definition keeps its bytes. It is real-money behaviour, hence Proposed and not a default |

## 3. Alternatives considered

| Alternative | Why it lost |
| :--- | :--- |
| **A new state `AWAITING_TRIGGER`** beside `AWAITING_RANGE` | A second wait with the same rows, the same watches off, the same restart, the same entry: every hand-written state set and its guard would classify it, for a difference the gate already names (`EntryGate.TRIGGER_NOT_MET`). |
| **Rename `AWAITING_RANGE` to `AWAITING_ENTRY`** | The truer name; it is a migration of every saved bot record and of the stored lifecycle values for a word. Kept as a follow-up if the owner wants it. |
| **Trigger on a crossing** (activate when the price crosses the trigger, either way) | That is a stop order, not a limit order; the owner said limit. A LONG started below its trigger would wait for a rise and then buy higher. |
| **A persisted "triggered" flag** for the latch | The lifecycle already latches: only `AWAITING_RANGE` asks. A flag is a second source of the same fact. |
| **A flat Resume ignores the trigger** | Simpler; but a bot that halted before it ever traded would then enter at a price the owner's limit forbids. |
| **NEUTRAL waits until the price touches the trigger** | A plausible meaning (start centred on a price), but it is not "better than"; asked as O1 instead of guessed. |

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | **NEUTRAL.** A NEUTRAL grid has no better side, so a trigger is refused. Would the owner want one meaning "wait until the price reaches X, from either side, then start centred there"? Recommendation: **no for now**: it is a different order type (a touch, not a limit); add it as its own task if asked. | nothing (refusal is the safe default) | 2026-10-22 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2, D3, D4, D6 | [EPIC-046A](completed/EPIC-046A_the_trigger_gates_the_entry.md) | Verified in the unit tier | `test_grid_entry_gate.py`, `test_a_grid_with_a_trigger_waits_for_a_better_price.py`, `test_grid_range_checks.py`, `test_grid_parameter_check.py`; mutation-checked (each comparison, the side, the gate, the flat Resume) |
| D5 (the Start check, the entry price, the host keys) | [EPIC-046A](completed/EPIC-046A_the_trigger_gates_the_entry.md) | Verified in the unit tier | `test_grid_range_checks.py`, `test_grid_entry_gate.py` |
| D5 (the editor, the status words, Discord, the backtest) | [EPIC-046B](incomplete/EPIC-046B_the_trigger_is_shown_and_backtested.md) | Not started | Not yet verified |
