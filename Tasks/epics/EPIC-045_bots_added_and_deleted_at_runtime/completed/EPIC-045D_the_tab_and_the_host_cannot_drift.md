# EPIC-045D — A guard maps each Bots tab action to a host verb

**Status:** ✅ Done (2026-10-21)
**Source:** the owner, 2026-10-21, quoted in the [epic README](../README.md)
**Risk:** 🟢
**Complexity:** S
**Epic:** [EPIC-045](../README.md)
**Depends on:** A, B

---

## 1. Context and problem
Nothing stops the Bots tab gaining an action the host cannot do, which is how `delete` and `new` drifted.

## 2. Acceptance criteria
- [x] A test lists every `*Command` the Bots tab dispatches, every lifecycle button and the menu actions, and maps each to a host verb or an explicit reasoned exclusion; an unmapped one fails (`tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py`, proven red on a seeded unmapped command).

## 3. Design
See [the decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D1..

## 3a. Reuse
None: test only.

## 4. Changes, per file
| `tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py`, `scanned_roots_registry_module_dependencies.py` | the guard and its registry row |

## 5. Testing
Red on a seeded unmapped command, a dropped command, a wrong verb, an undeclared verb and a reasonless exclusion; green on the tree. Tier: unit (architecture).

## 6. Docs touched
Only the epic's own files (README, TRACKING, decision record, task files); no `Docs/` page.

## Implementation notes (written when done)
The acceptance criterion was rewritten while building: it named `BotAction`, the New-bot flow and Arm/Disarm/Close-position; the delivered guard enumerates the `*Command` classes **defined** under `use_cases/` (nine, host requests left out) so a command fails however the tab imports it, and the Bots menu's command ids from `bots_commands`, so a new menu command fails too. Each command needs a `HostVerb` (the `HostControlAction`, the `bot <verb>`, its declaration in `cli_commands.json` and its row in the host's executor, all checked) or an `Excluded` with a reason. Menu actions that dispatch no bot command are listed by hand, which the guard cannot see; `BotAction` and the kind toolbar commands are checked against the code. It found **four gaps**, recorded as `OPEN GAP` exclusions rather than hidden, closed by [EPIC-045G](../incomplete/EPIC-045G_the_four_tab_actions_the_host_cannot_do_yet.md): a DRAFT's venue change (`ChangeBotVenueCommand`; today `bot delete` then `bot add`, a new bot id), confirm-resume of a HALTED bot at runtime (`run --resume-halted` is a flag of `run`, so it needs a host restart; review round 1 first filed it as excluded on purpose), and Arm and Disarm strategy (the trading module's armed-strategy controls, no bot id; the one-round headless command is `trade-once`). Seeded failures in the test file prove it can fail. The `-Full` result on the pull request head is Not yet read.

## Resume
Built and under review; this file is already in `completed/` with the pull request: flip nothing after the merge.
