# BOT-172 — The bot executor's port is split by audience, and GridExecutor is back under its ceiling

**Status:** ✅ Done (2026-10-08)
**Board:** `IBotExecutor` carried commands and facts together, so `GridExecutor` had 18 public members against architecture-rule §5.4's 15. The facts (fill, end, tick, price-age check, switch, stream gap and halt) are now the `IBotFacts` port, implemented by `GridFacts` and reached through `executor.facts`; the executor keeps the commands and has 13. Behavior is identical: every fact still posts through the executor's one guarded queue.
**Source:** the coordinator session, 2026-10-08, from the owner's Phase 1 leftovers: "Split the IBotExecutor port. GridExecutor has 18 public members, against 15 public methods in architecture-rule §5.4. This is a refactor … behavior stays identical, the tests stay green." Known since `EPIC-035C` (16 members) and `EPIC-035A` (17).
**Risk:** 🟡 — a pure restructuring of the actor every bot runs through; three Phase 2 sessions edit the same package.
**Complexity:** M — one new port, one new class, five consumers and about eighty test call sites change from `executor.on_x` to `executor.facts.on_x`.
**Epic (optional):** [EPIC-035](epics/EPIC-035_spot_grid_unattended_safety/README.md) (leftover of Phase 1)
**Depends on:** None

---

## 1. Context and problem
`GridExecutor` (`grid_executor.py`) held the user's commands, the lifecycle accessors and seven facts reported by handlers and watches. Interface Segregation (`architecture-rule.md` §1, §5.4): the router, the price watch and the stream watch never start or stop a bot, and the use cases never report a tick.

## 2. Acceptance criteria
- [x] `IBotExecutor` declares the commands and a `facts` accessor; the seven facts live in `IBotFacts`.
- [x] `GridExecutor` has at most 15 public members (13) and the facts are not among them.
- [x] Behavior is identical: every fact is posted through the executor's guarded queue; no test is weakened (the call sites only gain `.facts`).

## 3. Design
Composition, not multiple inheritance (`architecture-rule.md` §2): `GridFacts` is a second class built by the executor with its collaborators (`GridFactParts`, a frozen parameter object, since the facts act through the same placer, price reaction, gap, stopper, reconciler and interrupted-start instances the commands use) and the executor's own `_post` and `_forget_proposal`. The facts' bodies moved unchanged. Alternative rejected: leaving the facts on the executor and splitting only the ABC, which would not lower the class's surface.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/i_bot_facts.py` (new) | The `IBotFacts` port |
| `src/modules/bots/contracts/i_bot_executor.py` | The facts leave; `facts` accessor added |
| `src/modules/bots/application/services/grid_facts.py` (new) | `GridFacts`, `GridFactParts`: the facts and their worker-side bodies |
| `src/modules/bots/application/services/grid_executor.py` | Builds `GridFacts`; exposes `facts`; 13 public members, 247 lines |
| `bot_event_router.py`, `bot_price_watch.py`, `user_stream_watch.py` | Call `executor.facts.on_x` |
| `tests/unit/modules/bots/application/services/**` | `executor.facts.on_x`; `test_grid_executor_surface.py` locks the ceiling and the split |
| `Docs/HLD/03_module_contracts.md` | The port row names both ports |

## 5. Testing
`tests/unit/modules/bots` and `tests/integration/modules/bots` and `tests/unit/architecture` (2,092 passed) before and after the split; the new `test_grid_executor_surface.py` fails if a fact returns to the executor or the surface passes 15. Commit tier PASS. The `-Full` run on the PR head is read from its job logs.

## Implementation notes (written when done)
Pure move: the seven fact bodies and their four private helpers (`_apply_fill`, `_apply_end`, `_apply_switch`, `_reclaim_lease`, `_level_fill`) are `GridFacts`'s; the only new line of logic is `_forget_proposal`, which the switch-off handler calls where it used to assign `self._proposal = None`. Work left to a reviewer session per ONBOARDING §7 (a refactor is a feature-type PR).
