# EPIC-047D — The desktop reaches the bridge over SSH from a connection profile set in the Options page

**Status:** 🔵 Backlog
**Source:** the owner's request of 2026-10-24 (O6: a configurable connection with selectable protocols) and delegation, settled as G1; [the SSH client record](../DECISION_2026-10-24_the_ssh_client_is_asyncssh.md) D1–D5; charter D5.
**Risk:** 🟡 — a new dependency and a credentials-adjacent setting; no trading rule changes, and the profile stores no secret.
**Complexity:** L — the transport adapter, the reconnect, the profiles store, the Options page, and a measurement on the owner's Windows.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047A](../completed/EPIC-047A_the_wire_codec_and_the_version_handshake.md) (codec), [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md) (the bridge to talk to)

---

## 1. Context and problem
The desktop needs a transport behind a seam: SSH in v1, other protocols later (O6). De-risk R3 on the owner's Windows against the VPS: key-file login, host-key pinning, round trip (asyncssh p50 25.6 ms, p95 65.4 ms) and "no listener" pass; the agent path is untested (no agent held the key); the reconnect took 1909 ms. A1 was false until the owner installed a key, for root. Two traps: `client_keys=None` turns key login off; a blocking call in the client's loop inflated event latency to p95 3.0 s (DERISK §3.3).

## 2. Acceptance criteria
- [ ] A transport seam (a port) with one adapter, `asyncssh`; the Bots screen and the tab know no transport. The SSH loop runs on its own thread with no blocking call inside it (`async-ui-action-rule.md`); a test fails on a blocking call in that loop.
- [ ] **Dependency (ONBOARDING §7):** `asyncssh` is added to `requirements.txt`, `requirements.lock` is regenerated with the compile command in its header, the pinned version is the one CI resolves, and the pull request body names the dependency and the transitive change to `cryptography` for the owner's veto (SSH record D2). `requirements-headless.txt` is unchanged.
- [ ] A **connection profile** holds: name, host, port, user (`sew`), the protocol, a reference to a key file or the agent, timeouts and the reconnect policy; the app stores **no password, passphrase or key** (AC9). An Options page creates, edits, deletes a profile and switches its protocol with no code change.
- [ ] Host keys are pinned through `known_hosts`; a wrong key is refused with a sentence naming the host (a test with a wrong key); first use without the key in `known_hosts` says what to do.
- [ ] A profile with no key file never passes `client_keys=None` to `asyncssh.connect` (a test covers the trap).
- [ ] **Windows agent login** works through Pageant and through the Windows OpenSSH agent service, tested on the owner's machine with the key loaded into the agent; the result is recorded. If it fails and `paramiko` passes, the fallback rule (SSH record D5) applies and the owner is told.
- [ ] **Reconnect after an abrupt cut takes under 2 s** on the real link (1909 ms measured); the slim bridge entry point of 047C is part of it. The time is recorded from the owner's VPS.
- [ ] The desktop sends a heartbeat at a third of the bridge's idle watchdog; a half-open link is noticed and the tab says "disconnected, data as of …" (AC6). A command in flight at the cut is not sent twice.
- [ ] A transport error is a typed error shown in words: refused key, unknown host key, host unreachable, version difference (047A's wording).

## 3. Design
The seam now, the variants later (P7): a transport port with the `asyncssh` adapter; a Unix socket, a VPN or a TLS endpoint are other adapters, not built. The profile store follows the repository's existing settings and Options-page mechanism rather than a new one (P5); credentials are references only. The loop on its own thread fenced per `async-ui-action-rule.md`.

## 3a. Reuse
Options pages: `alerting/ui/options` and `trading/ui/settings` are the shapes to mirror; `.claude/rules/capabilities.md` for the settings store and the shared widgets: `used <symbol>` for each, recorded at start. Presenter fencing: `fenced_reads.py` shapes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `requirements.txt`, `requirements.lock` | `asyncssh`, with the owner's veto point in the PR body |
| `src/…` (transport port and adapter, profiles store, Options page) | the transport and the profiles |
| `tests/…` | transport tests against a fake bridge; the profile store; the trap test; the loop test |

## 5. Testing
Tier: unit and offscreen UI, then the full gate. The Windows agent and the real-link reconnect run once on the owner's machine and are recorded with their output. Not run.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` through [EPIC-047G](EPIC-047G_the_runbook_for_the_vps_link.md); `Docs/HLD/11_desktop_workbench.md` if the Options pages are described there.

## Implementation notes (written when done)
Not written: not started.
