# EPIC-038J — Control of a running host (only if the owner wants it, and through the channel the owner picks)

**Status:** 🔵 Planned — **gated**: do not start until decision O4 is answered and `EPIC-036F` has merged
**Source:** the owner, 2026-10-09; the research found that a second process is read-only by design (`EPIC-035H`) and a status needs no control, so *changing* what a live host runs is a separate security surface (R11).
**Risk:** 🔴 — a new path by which something can stop or start a bot; every documented mistake in the sources lives here
**Complexity:** L — a command source, authorisation, idempotency, audit
**Epic:** [EPIC-038](../README.md)
**SPEC:** SPEC-015 (new, 038D) is updated.
**Design:** [DESIGN §9](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§11](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [O4](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** 038D; [`EPIC-036F`](../../EPIC-036_alerting_module/incomplete/EPIC-036F_remote_control_from_discord.md) (its `IRemoteCommandSource`, allowlist, tiers and audit are reused, not rebuilt); [`EPIC-035X`](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) (the audit trail); owner decision O4.

---

## 1. Context and problem
In v1 the way to change what runs is to stop the host, `bot apply` and start it again — one path, nothing to authorise. If the owner wants to stop one bot on a live host from a shell, a command must cross from a second process into the first. The first is the writable copy; the second is read-only and may not place or cancel anything, which is exactly why a plain CLI cannot do it. The options (O4): none, a spool directory the host polls, a local socket or named pipe, or Discord only via `EPIC-036F`.

## 2. Acceptance criteria
- [ ] The owner's choice (O4) is recorded; this task builds **only** that channel (recommended default: none in v1, remote control = `EPIC-036F`, in which case this task is closed as superseded with the reason at the top of the file, per `Tasks/epics/README.md`).
- [ ] Whatever the channel, a command reaches the host as a source of commands calling `ICommandDispatcher` (the UI's own handlers), once (idempotency key), and is audited (`EPIC-035X`); there is no second implementation of Stop.
- [ ] Authorisation is explicit: a local channel is restricted to the service account by file or pipe permissions; a remote channel uses `EPIC-036F`'s user-ID allowlist (never a webhook, never a group); an empty allowlist means no control.
- [ ] No TCP port is opened. A test asserts the host's listening sockets are empty.
- [ ] A command's tier is enforced (status and pause low; stop and delete high with an extra confirmation) per `EPIC-036F`.
- [ ] A malformed, replayed or unauthorised command is logged and refused without effect.

## 3. Design
A new `ICommandSource` registers with the host the way a signal source does (open/closed): the host owns the dispatch, a source owns the transport. A spool directory is the simplest (a file per command, atomic rename, the host deletes it after dispatch) and has the same attack surface as the file permissions; a socket is faster and needs authentication; Discord reuses an audited design. The recommendation avoids building a second one.

## 4. Changes, per file
To be written once O4 is answered.

## 5. Testing
To be written once O4 is answered; the criteria above name the cases (replay, unauthorised, malformed, idempotent, audited, no open port). Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. Blocked on O4 and `EPIC-036F`.
