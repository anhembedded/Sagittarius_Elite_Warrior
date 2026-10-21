# EPIC-045D — A guard maps each Bots tab action to a host verb

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-21, quoted in the [epic README](../README.md)
**Risk:** 🟢
**Complexity:** S
**Epic:** [EPIC-045](../README.md)
**Depends on:** A, B

---

## 1. Context and problem
Nothing stops the Bots tab gaining an action the host cannot do, which is how `delete` and `new` drifted.

## 2. Acceptance criteria
- [ ] A test lists every `BotAction`, the New-bot flow and the Arm/Disarm/Close-position actions and maps each to a `HostControlAction` or an explicit reasoned exclusion; an unmapped action fails.

## 3. Design
See [the decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D1..

## 3a. Reuse
None: test only.

## 4. Changes, per file
| `tests/unit/architecture/` | the guard |

## 5. Testing
Red on a seeded action, green on the tree.

## 6. Docs touched
none
