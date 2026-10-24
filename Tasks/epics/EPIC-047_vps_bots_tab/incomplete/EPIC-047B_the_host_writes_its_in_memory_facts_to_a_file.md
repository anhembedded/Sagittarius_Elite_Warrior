# EPIC-047B — The running host writes the facts only it holds to a file when they change

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24, settled as G7a; [the remote link record](../DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D4; De-risk R2 §2.5.
**Risk:** 🔴 — it changes the real-money host, even though it only writes a file; a write that blocks, tears or leaks a key would be a defect on the trading host.
**Complexity:** M — one writer beside `health_snapshot.py`, four fact groups, owner-only atomic writes.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-048A](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048A_the_doors_rule_and_its_guard.md) and [EPIC-048B](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) (the epic's prerequisite)

---

## 1. Context and problem
A bridge is a second process: it reads the store's files and sends commands through `DirectoryHostControl`, and it can reach nothing the running host holds in memory (DERISK §2.5). The Bots screen needs four groups of those facts: the **trading leases** (which symbol is held by which bot or by the Trade tab, the occupancy of `GetBotRunFactsQuery`), the **enabled venues**, the **budget caps** and the **exchange facts** the host already reads. Without a socket there is one honest path: the host writes them to a file, as it writes `state/health.json` every 10 s (`health_snapshot.py`, `HEALTH_INTERVAL_SECONDS`). The bridge must not call the exchange itself: it would add REST weight on the account and IP the bots use, and it would hold the host's keys.

## 2. Acceptance criteria
- [ ] The host writes one facts file when a fact changes (and at a bounded interval as a heartbeat), under `state/`, owner-only (0600) and atomically (temp file and rename), as `state/health.json` is.
- [ ] The file carries the four fact groups, a `schema` name and a monotonic revision, and the host's clock time; a reader that finds a torn or older revision keeps the last good one.
- [ ] It carries **no key, no secret and no credential**; a test reads the file for a venue that has a stored key and finds only the connection state ("a key is saved").
- [ ] The write never blocks the trading path: a slow or full disk delays the file, not an order or a stop (a test with a blocked writer; a log line names the failure).
- [ ] The bridge's `GetBotRunFactsQuery` and `GetVenueChoicesQuery` answers (EPIC-048B) can be built from this file and the store's files alone.
- [ ] No trading behaviour changes: the host's existing tests are unchanged and green, and a run on the fake exchange places the same orders.
- [ ] The file is written on the Linux VPS profile and on the desktop host; deleting it is harmless (the host rewrites it).

## 3. Design
The mechanism is the repository's own `health_snapshot.py` and its writer (P5, mirror a vetted shape): the facts are a read model of host state, written on change. One writer, in the host's application layer (`operations`), the technical write in `support/` (charter G8: the bridge lives in the app). The file is a stored-file contract, so its codec is hand-written and version-tolerant (EPIC-047A's note on stored files).

## 3a. Reuse
`health_snapshot.py` and `HEALTH_INTERVAL_SECONDS`: `used` for the atomic writer and the schedule; the occupancy logic of `BotRunFactsReader`: `used` after EPIC-048B moves it. Catalog rows checked in `.claude/rules/capabilities.md` when the task starts.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/operations/…` | the facts model and the publisher beside the health snapshot |
| `src/support/…` | the owner-only atomic file write (reuse if it exists) |
| `tests/…` | the file's schema, the no-secret test, the non-blocking test |

## 5. Testing
Tier: unit and integration on the fake exchange, then the full gate. Each criterion maps to one test; the no-secret test plants a key and searches the bytes. Not run.

## 6. Docs touched
The `operations` module's design page if it has a folder under `Docs/MODULES/`; `Docs/OPERATIONS/headless_runbook.md` names the file in [EPIC-047G](EPIC-047G_the_runbook_for_the_vps_link.md). Otherwise `none, because …`, written when the task closes.

## Implementation notes (written when done)
Not written: not started.
