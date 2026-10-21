Status: Current

# 003 — Authorising a remote command: one gated door for a trading app

**Teaches:** who may tell a trading app what to do from a phone, and how to make a mistaken or hostile command cost as little as possible. **Decision:** [`DECISION_2026-10-21_remote_control_from_discord.md`](../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-21_remote_control_from_discord.md) (accepted by the owner, 2026-10-21, `EPIC-036F`). This page teaches; the record decides.

## 1. The problem
An alert says a bot halted. The owner is away and wants to answer. The same door that lets the owner stop a bot lets anyone with the same access do it, a command can arrive twice, and an app that trades real money must not turn "I tapped something" into "I opened a position".

## 2. Constraints
- The app must not listen on a port: a public endpoint on a trading host is a bigger target than any chat integration.
- Authorisation cannot rest on where a message came from; a channel, a group or a role changes hands.
- The commands already exist and carry the app's own safeguards (the single-instance lock, Start preconditions, resume's two steps); a second implementation of them would drift.
- Whatever the door does must leave a record, written before and after.

## 3. Solutions considered
| Option | What it is | Why it lost or won |
| :--- | :--- | :--- |
| Webhook as a command path | Post to the chat, the app reads it | A webhook has no identity; anyone with the URL is the owner. Never |
| Authorise by channel or role | "Anyone in #ops may stop a bot" | Adding the bot to a server, or a role grant, hands over control |
| HTTP interactions endpoint | Discord calls the app | Needs an inbound port and a signature library |
| **Outbound gateway + allowlist of user ids + one gate** | The app connects out; each command carries the sender's id | **Chosen (accepted by the owner, 2026-10-21):** identity is the user id Discord signs into each event; nothing listens |

## 4. The choice and why
One class, the **gate**, stands in front of the command handlers. Every remote command passes the same five steps in order: *is this user on the allowlist* (an empty list refuses all), *has this request id been spent* (durable, so a restart cannot replay it), *which tier is the command* (status, pause and stop at once; start and resume not remotely in the first release), *audit before*, *run through the UI's own dispatcher*, *audit after*.

## 5. How it is implemented
See the sequence diagram in the decision record, §4. The receive side is a port of its own (`IRemoteCommandSource`) beside the send side (`IAlertChannel`), so a channel that can only send (Telegram today) stays simple. A guard test fails if a handler can be reached without the gate.

## 6. Risks and failure modes
- A taken-over allowlisted account: the first release can only pause or stop, and a stop keeps the base asset instead of selling it at market.
- A command whose id was spent but whose result was never recorded (a crash in between): reported as unknown, never re-run.
- The audit trail is a dependency: without it the design promises no remote command, so the task waits for it.

## 7. Limits
Allowlist by user id is only as strong as the account behind the id. When the app ever needs a second approver, or commands from a place with no chat identity, this stops being enough and the question becomes four-eyes approval, not a better gate.

## 8. Names to know
*Anti-corruption layer* and *facade* (the gate in front of the handlers), *idempotency key* (the request id), *least privilege* and *tiered authorisation* (what each command may do), *confused deputy* (why authorising by channel fails), *outbound-only* connection (no listening port), *audit before and after* (write-ahead record).

## 9. Interview questions
1. *Why not authorise by the Discord channel?* A channel is a place, not a person: membership changes, the bot can be added elsewhere. Identity must travel with each command.
2. *How do you stop a command running twice?* An idempotency key (the interaction id) is recorded durably before the action; a repeat finds it spent.
3. *Why is the first release status, pause and stop only?* Least privilege: the worst a stolen account can do is stop bots, never trade. Moving money needs a second decision.
4. *Why must a remote stop not sell?* Selling is a market order that realises a loss; a remote command should be reversible by the owner at the desk.
5. *Why not simply write a small Discord client?* The gateway protocol (heartbeat, resume, rate limits) changes and a bug is a missed stop; a maintained library is cheaper than owning it, at the price of one pinned dependency.

## 10. Read more
- OWASP, *Authorization Cheat Sheet* (least privilege, deny by default).
- Discord developer documentation, *Gateway* and *Interactions* (what the platform signs and what it does not).
