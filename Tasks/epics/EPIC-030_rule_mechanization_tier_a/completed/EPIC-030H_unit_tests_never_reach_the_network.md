# EPIC-030H — Unit tests cannot reach the network

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — May expose hidden network use
**Complexity:** S — delivered in PR 3
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
`ci-rule.md` §2 forbids network in unit tests; nothing enforced it.

## 2. Acceptance criteria
- [x] Any non-loopback connect from `tests/unit` raises before a packet leaves; loopback, `AF_UNIX` and asyncio keep working.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/conftest.py`, `tests/unit/network_block.py` | Refuse non-loopback connect, datagrams and name lookups (including the legacy `gethostbyname` family) |
| `tests/unit/test_unit_tests_never_reach_the_network.py` | Probes for each refusal and for loopback still working |

## 5. Testing
Unit probes; removing the new patches turns them red (5 for name lookups and datagrams).

## Implementation notes (written when done)
Delivered in pull request #323 and PR 3. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
