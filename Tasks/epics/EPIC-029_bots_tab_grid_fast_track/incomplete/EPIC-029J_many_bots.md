# EPIC-029J — Many bots run at once, one per symbol, each within its own budget

**Status:** 🔵 Backlog — after the fast track; sliced in detail when it starts
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §4.3 "After the fast track", accepted by the user on 2026-10-03 (*"Oki, duyệt"*).
**Risk:** 🟡 — concurrency across several actors and several budgets on one account.
**Complexity:** M — lift the runtime cap, measure tick fan-out, per-bot PnL attribution across bots.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029H`.

---

## 1. Context and problem
ADR D20 caps the fast track at one RUNNING bot as a runtime check. The entity, ids, store, tags and budgets are already per bot, so this task lifts the cap and proves isolation.

Both checks Start runs today, the cap (`other_active_bot`) and the symbol's lease, see only the bots of one data root. Two copies of the app (the desktop and the headless host, each with its own data root) can therefore run a bot on the same account and the same symbol, and neither refuses: their orders, the Futures one-way position (netted per symbol for the whole account) and the account balance would be shared without either knowing. Today the copies trade different accounts (the host Spot mainnet, the desktop Futures Testnet), so nothing collides; the gap opens the day both hold the same account. Owner question, 2026-10-16: why a second bot on the same symbol is refused while a bot on another venue runs.

## 2. Acceptance criteria
- [ ] Several bots run on different symbols of one venue; each one's orders, fills and PnL are attributed by its tag and never by another's.
- [ ] Starting a bot on a symbol another bot holds is refused, naming the holder (the lease).
- [ ] Tick fan-out to N bots is measured (N = 1, 5, 20) before the cap is raised; the result is recorded and the chosen cap justified by it.
- [ ] An Emergency Stop halts every bot on that venue and none on the other.
- [ ] A bot started on an account and symbol a bot of **another copy of the app** already trades is refused or warned, naming that holder; the mechanism (for example an exchange-side marker such as the client order id tag prefix, or an account-scoped lease) is chosen when the task starts, and a test with two data roots on one fake account proves it.

## 3. Design
Each bot keeps its own actor (ADR D9); the event handlers route by tag. The measured fan-out decides whether events are filtered by symbol before queueing. The full per-file design is written when this task starts, against the tree as it is then.

## 4. Changes, per file
Written when the task starts (the fast track will have changed the files it touches).

## 5. Testing
Written when the task starts; each criterion above maps to a unit or integration test, plus the Testnet tier where an exchange behaviour is involved.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
