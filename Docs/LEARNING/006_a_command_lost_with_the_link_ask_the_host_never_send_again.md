Status: Current

# 006 — A command lost with the link: ask the host, never send it again

**Teaches:** what to do when you sent a command that moves real money and the connection died before you heard back — at-most-once delivery, idempotency, and why a "fence" makes "it never arrived" a fact instead of a guess. **Decision:** recorded in [`EPIC-047E`](../../Tasks/epics/EPIC-047_vps_bots_tab/completed/EPIC-047E_the_vps_bots_tab.md) (PR 3a, the coordinator's decision of 2026-10-28; the owner may veto). This page teaches; the record decides.

## 1. The problem
The desktop sends *Start* to the VPS host. The link is cut. The desktop has no answer. Did the bot start? If the desktop sends it again and the first one had in fact arrived, a ladder may be laid twice; if it does nothing and the first one is delayed in a buffer somewhere, the bot may start minutes later, when the person has moved on and no one is typing the real-money confirmation any more.

## 2. Constraints
- A command can be lost on the way, lost on the way back, or merely slow: the sender cannot tell which from where it stands.
- The host's gate and audit are the only truth about what ran; the desktop must not guess.
- A real-money command must always follow a fresh answer to the real-money question.
- Stop and Pause only reduce exposure, but a re-send is still a decision, not a reflex.

## 3. Solutions considered
| Option | What it is | Why it lost or won |
| :--- | :--- | :--- |
| Send again, same id | The host remembers ids, so a repeat is refused if it already ran | A command that never arrived would run late, without a fresh confirmation |
| Send again, new id | Retry as a new request | Can run twice |
| Auto-resend only Stop and Pause | They are safe to repeat | Kept as a later choice for the owner; not needed to be safe |
| **Ask the host what it recorded, never re-send** | One read-only `outcome` call: ran, refused, never reached, or still waiting | **Chosen:** the answer comes from the audit, and a re-send is only ever a new action of the person |

## 4. The choice and why
After the link is back, the desktop asks the host for the recorded outcome of each id it had no answer for. If the host never saw the id, the host first writes a *fence* — an audit line saying that id is expired — so that "never reached" stays true even if the old connection's bytes are delivered later. A fenced id can never run afterwards; the person who still wants the command types it again, which is a new request with a new id and a new confirmation.

## 5. How it is implemented
`shell/vps_link/command_reconciler.py` → `CommandReconciler` asks, `support/wire/bridge/bridge_outcome_call.py` → `serve_outcome` answers on the host, `modules/operations/adapters/directory_host_control.py` → `DirectoryHostControl` reads the audit and writes the fence, and `jsonl_host_control_audit.py` → `JsonlHostControlAudit` makes `has_seen` honour a fence written by another process. The unanswered ids live in `shell/vps_link/unanswered_ledger.py` → `UnansweredLedger`; until one is settled the bot accepts only Stop and Pause. Add to VPS (`SPEC-018`) uses the same door and the same rule: a reply that never came is told as "may or may not have been created", and nothing is sent again.

## 6. Risks and failure modes
- The ask itself can fail (link lost again): the ledger is left as it was and the person is told.
- A fence changes a read into a write; it only ever makes an id refuse to run, so it is reversible in effect.
- An older host without the call: the ledger stays and says so; the person reads the audit.

## 7. Limits
This is at-most-once delivery with an honest unknown. When a command must be delivered despite cuts (a stream of orders, say), the answer is an idempotent command with a durable outbox on both sides, not this.

## 8. Names to know
*At-most-once vs at-least-once vs exactly-once delivery*, *idempotency key*, *fencing token* (here the fence line), *tombstone*, *write-ahead audit*, *read-your-writes*, *two generals problem* (why the sender cannot know).

## 9. Interview questions
1. *The connection dropped after you sent a payment. What do you do?* Do not blindly retry; query the authority for the outcome of the id, and retry only with the same idempotency key if the authority dedups.
2. *Why is "same id again" not enough here?* If the first send never arrived, the host would run it now, late, without the confirmation the person gave then.
3. *What does the fence buy?* It turns "I saw nothing" into "that id will never run", closing the window where a delayed packet from the old connection still lands.
4. *Is exactly-once possible?* Only as at-least-once delivery plus idempotent handling; here we choose at-most-once and surface the unknown.
5. *Why can Stop and Pause still be sent while a command is unsettled?* They only reduce exposure and are harmless to repeat; the control that lowers risk is never the one withheld.

## 10. Read more
- Martin Kleppmann, *Designing Data-Intensive Applications*, chapter 8 (the trouble with distributed systems) and the section on fencing tokens.
- Stripe, *Designing robust and predictable APIs with idempotency*.
