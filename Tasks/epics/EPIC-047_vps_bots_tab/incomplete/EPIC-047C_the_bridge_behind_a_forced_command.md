# EPIC-047C — A bridge process on the host, started by `sshd` behind a forced-command key, serves the Bots queries and commands

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24, settled as G7 and G10; [the remote link record](../DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D2, D3 and D5; De-risk R2, R5.
**Risk:** 🔴 — it is the only door from the desktop to a real-money host; a command that bypassed the host's gate, a shell the key should not give, or a listener would break the epic's constraints.
**Complexity:** L — the bridge entry point, the event stream, the commands, the watchdog, and the forced-command key.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047A](EPIC-047A_the_wire_codec_and_the_version_handshake.md) (codec, handshake), [EPIC-047B](EPIC-047B_the_host_writes_its_in_memory_facts_to_a_file.md) (the facts file)

---

## 1. Context and problem
`sshd` can start a command for each session, listening on nothing. De-risk R2 showed that a key restricted with `restrict,command="…"` runs only the bridge: a request for `whoami; cat /etc/passwd` returns the bridge's `hello`, a port forward is "administratively prohibited", a terminal is refused, and the bridge ends with the connection (0 left, 6 of 6 runs); a half-open link left 1 bridge after 10 s without a heartbeat and 0 with a 6 s idle watchdog. The bridge's start is dominated by imports: 258–269 ms of ~340 ms; the real reconnect was 1909 ms (DERISK §3.7).

## 2. Acceptance criteria
- [ ] The bridge is started by `sshd` for each session as the **`sew`** account through `DirectoryHostControl`'s directory; it speaks newline-delimited JSON on stdin and stdout in the protocol of the remote link record (hello, welcome, calls with ids, events with a sequence).
- [ ] A **slim entry point** imports only the wire layer, the store reader and the control-door client; its import time is measured on the VPS and recorded (target: with the transport, reconnect under 2 s, see [EPIC-047D](EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md)).
- [ ] Reads: the store's files and the facts file of 047B only; the bridge calls no exchange and loads no key (a test runs it with no key store and no network).
- [ ] Changes: one `BotChangedEvent` per write to a bot's file, found by polling the directory (the spike: one `scandir` per 100 ms; p50 52 ms, p95 ≤ 100 ms); snapshot then subscribe converges after a forced cut (6 of 6 in the spike).
- [ ] Commands go through `DirectoryHostControl`, as the CLI does: the host's gate, audit, replay and expiry checks are the one door; a command adds up to ~1 s (the host's poll); the result carries the host's verdict and the audit reference; a command sent twice after a reconnect does the work once (the request id).
- [ ] An idle watchdog (6 s in the spike) ends a bridge whose client froze; a test freezes a client with no FIN and finds 0 bridges after the watchdog.
- [ ] The bridge opens **no socket** (TCP, UDP, Unix): a test lists the process's sockets with `ss`; AC5's guard test stays green.
- [ ] The restricted key, installed as in the runbook, runs only the bridge: a check asks it for a shell, a port forward and a terminal and gets the bridge's `hello`, "administratively prohibited" and a PTY refusal. Evidence from the owner's VPS, recorded in the notes.
- [ ] A version difference gets "refused" and exit 3 before any read (047A).

## 3. Design
Mirror the repository's `bot show` pattern (read the files) and its control door; the forced command is OpenSSH's own mechanism (P5; sources in DERISK). The bridge is a second process, not a thread in the host (G7, record D2): it cannot slow the bots and ends with its session. The bridge lives in the app, not the Engine (G8). The `authorized_keys` line is an operator step, written in [EPIC-047G](EPIC-047G_the_runbook_for_the_vps_link.md), not by code.

## 3a. Reuse
`ReadOnlyBotStore`, `DirectoryHostControl`, `HostCommandProcessor`, `health_snapshot.py`: `used`. The Engine's `TraceServer` envelope: studied as a model, not changed (G8). Confirm each against `.claude/rules/capabilities.md` at start.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/…` (bridge entry point under `operations` or `support/`, chosen at start) | the slim entry point and the serve loop |
| `deploy/linux/…` | a launcher the forced command names, if one is needed |
| `tests/…` | protocol tests on a fake host directory; the no-socket test; the watchdog test |

## 5. Testing
Tier: unit and integration (a fake host directory and an in-process pipe), then the full gate. The restricted-key checks run once on the owner's VPS and are recorded; they are not in CI. Not run.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` (the bridge, in 047G); the `operations` module page if it has a folder.

## Implementation notes (written when done)
Not written: not started.
