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
none

## Implementation notes (written when done)
The guard scans the Bots tab's UI for every `*Command` it imports from the bots use cases (nine) and requires a `HostVerb` (the `HostControlAction`, the `bot <verb>` and its declaration in `cli_commands.json`, all checked) or an `Excluded` with a reason. Menu actions that dispatch no bot command are listed by hand, which the guard cannot see; `BotAction` and the kind toolbar commands are checked against the code. It found **three gaps the owner may want closed with a verb**, recorded as exclusions rather than hidden: a DRAFT's venue change (`ChangeBotVenueCommand`; today `bot delete` then `bot add`), and Arm and Disarm strategy (a strategy-module act with no bot id). `ConfirmBotResumeCommand` is excluded on purpose (decision D13; `run --resume-halted` answers it). Mutation-checked by five seeded failures in the test file itself. The `-Full` result on the pull request head is Not yet read.

## Resume
Built and under review; this file is already in `completed/` with the pull request: flip nothing after the merge.
