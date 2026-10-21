# EPIC-045E — The runbook's add-a-bot procedure is export, scp, `bot add`, `bot start`

**Status:** 🟡 In progress
**Source:** the owner, 2026-10-21, quoted in the [epic README](../README.md)
**Risk:** 🟢
**Complexity:** S
**Epic:** [EPIC-045](../README.md)
**Depends on:** A, B

---

## 1. Context and problem
Runbook §6 says delete is not a running-host command; §8 says adding a bot needs the host stopped.

## 2. Acceptance criteria
- [ ] §6 documents `bot add` and `bot delete` and drops the line that says delete is not a running-host command.
- [ ] §8's add-a-bot procedure reads export, scp, `bot add`, `bot start`, with no restart, and says what `bot add` records (no desired state).

## 3. Design
See [the decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D2, D3..

## 3a. Reuse
None: documentation only.

## 4. Changes, per file
| `Docs/OPERATIONS/headless_runbook.md` | §6, §8 |

## 5. Testing
Document guards and `python3 scripts/check_skill_prompt_references.py`.

## 6. Docs touched
the runbook
