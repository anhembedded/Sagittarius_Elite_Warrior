# ADR — The remote link cuts in at the application's doors and reaches the host through a bridge process behind a forced-command key

**Epic:** [EPIC-047](README.md)
**Date:** 2026-10-24
**Status:** Accepted
**Decided by:** the owner's delegation of 2026-10-24, through the coordinating session: *"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"* (translated: "decide them for me, consistent with the whole Constitution"). Settled as G6, G7, G7a and G10 of the [charter](CHARTER.md) §4 (v0.4 decided G6 and G7 provisionally; v0.5 reworded them and added G7a and G10 after De-risk). The owner asked for this record, with this status, on 2026-10-24. The Constitution check is §2a. The owner may veto any row.
**Supersedes / superseded by (optional):** none. Read with [the SSH client record](DECISION_2026-10-24_the_ssh_client_is_asyncssh.md) (G1) and [EPIC-048's record](../EPIC-048_ui_reaches_the_application_through_its_doors/DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) (G9).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | measured in [`DERISK.md`](DERISK.md) at `5ddbd68` or on the owner's run of 2026-10-24; cited by section |
| 🤖 Agent decision | delegated by the owner and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context

The owner wants the Bots tab on the VPS host, with the host's own checks and audit, and with the host listening on no Internet-facing port (EPIC-036F D3; charter §5.1). The host (`sew-run`) is the only writer of its bots.

**Established facts** (`5ddbd68`, DERISK):

- ✅ **R1.** The Bots detail built from six reads that crossed a JSON wire **equals** the one built in process (frozen-dataclass equality); 6 queries, 663 bytes, 11.8 ms to encode and decode. The seam is the existing dispatcher plus two new queries, `GetBotRunFactsQuery` and `GetVenueChoicesQuery`, and the event stream (§1.3). `detail_for` is a pure function of nine inputs, seven of them host facts. The Plan re-judges 150 ms after the last keystroke (`presenter_pacing.py:23`), so a host-computed detail would make each edit an SSH round trip (§1.5).
- ✅ **R2.** A bridge started by `sshd` listens on **no socket** (TCP, UDP or Unix), on localhost and on the owner's VPS (§2.3, §3.8). A key restricted with `restrict,command=…` runs only the bridge: a request for `whoami; cat /etc/passwd` gets the bridge's `hello`, a port forward is `administratively prohibited`, a terminal is refused. The bridge ends with the connection (0 left after 0.5 s, 6 of 6 runs).
- ✅ **R2, §2.5.** The running host has no socket for a second process to dial (Docker's `dial-stdio` dials a listening Unix socket). A second process reaches the bots by reading the store's files, as the read-only `bot list` and `bot show` do, and sends commands through `DirectoryHostControl` (the host polls every 1 s). It cannot reach the facts only the running host holds in memory: symbol leases, enabled venues, budget caps, the exchange's answers.
- ✅ **R3, §3.8.** On the owner's Windows against the VPS, the key was installed for **root**, not `sew`; the desk must not log in as root. `PasswordAuthentication` was still on.
- ✅ **R4.** The 15 contract roots are **45 records, 225 fields, 14 enums and 3 tagged unions**. One reflective codec is about 140 lines in the spike, against about 550 hand-written lines.
- ✅ **R5.** Change-to-desk latency p95 ≤ 100 ms (poll-bound; p50 52 ms); 6 of 6 forced cuts converge. A frozen laptop leaves a half-open link: without a heartbeat 1 bridge was left after 10 s, with a 6 s idle watchdog 0.
- ✅ **R6.** A version mismatch is refused in words and the bridge exits 3. A hash over Python module paths changes when a class moves with the wire unchanged. One contract hash can say only "same" or "different".

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **G6. The link cuts in at the application's doors.** Every host fact reaches the desktop through a query or a bus event: the six reads the detail is built from, plus `GetBotRunFactsQuery` (the host computes the occupancy, since it knows its own bots and symbol leases) and `GetVenueChoicesQuery` (connection state only, never a key). The **pure assessment** over those facts (readiness, ladder, earnings) lives in the application layer and **runs on the desktop**. Commands reach the host through `IHostControl`, so the host's gate, audit, replay and expiry checks stay the one door. | Accepted | Agent, owner's delegation | Evidence R1. The screen needs the doors to be narrow first: [EPIC-048A and 048B](../EPIC-048_ui_reaches_the_application_through_its_doors/README.md). The cost is two queries and one move of the pure assessment. |
| D2 | **G7. v1 is SSH only, and the host listens on no socket.** The desktop runs a **bridge**: a second process on the host, started by `sshd` for each session, speaking newline-delimited JSON on stdin and stdout. It reads the store's files, publishes a bot's change as one `BotChangedEvent` per write (detected by polling the directory), and sends commands through `DirectoryHostControl`. The bridge is not "Docker's `dial-stdio`" (that dials a listening socket). A 0600 Unix socket on the host, a VPN and an opt-in TLS endpoint are later variants behind the transport seam; the socket variant needs the owner's decision, since it reverses EPIC-038's "no socket" in spirit. | Accepted | Agent, owner's delegation | Evidence R2, R5. EPIC-038's "listens on no port" and its test stay. A command costs up to about 1 s (the host's poll); a change reaches the desktop in about 0.1 s plus the real round trip (p95 65.4 ms on the owner's link), about 0.17 s against AC2's 5 s. |
| D3 | **Identity.** The desktop logs in as the **`sew`** account, never as root. Its key is restricted in `sew`'s `authorized_keys` with `restrict,command="…"` so it can run only the bridge: no shell, no port forwarding, no terminal. The owner's root key stays their own administration key, outside the app's profiles. The runbook ([EPIC-047G](incomplete/EPIC-047G_the_runbook_for_the_vps_link.md)) sets up the key and turns `PasswordAuthentication` off once the key works. | Accepted | Agent, owner's delegation | Evidence R2, §3.8. A stolen desktop key can run the bridge and nothing else. A mistake in `authorized_keys` can lock the owner out, so the runbook keeps the current session open until a new key login works. |
| D4 | **G7a. The host writes the facts only it holds to a file when they change.** These are the trading leases, the enabled venues, the budget caps and the exchange facts it already reads. The file is written owner-only and atomically, as `state/health.json` is (`health_snapshot.py`), and the bridge reads it. The bridge **never calls the exchange and never holds a key**. | Accepted | Agent, owner's delegation | Evidence R2 §2.5: no other path without a socket. The host stays the single exchange client, so no REST weight is added on the account and IP the bots use. The cost: a change to the host ([EPIC-047B](incomplete/EPIC-047B_the_host_writes_its_in_memory_facts_to_a_file.md)), reviewed as code. |
| D5 | **G10. The link protocol.** Every message carries a **per-bot revision**, applied only when greater, so the order of a snapshot and an event does not matter. The desk sends a **heartbeat** at a third of the bridge's **idle watchdog** (6 s in the spike); the watchdog is the bridge's own and does not depend on `sshd`. The version handshake hashes explicit **wire names** (`schema` strings such as `sew.bot-snapshot/1`), not Python module paths. Wire forms come from **one reflective codec** plus one round-trip **contract test per root type**. The hand-written file codecs stay as they are, since a stored file must read across versions and the link is same-build. | Accepted | Agent, owner's delegation | Evidence R4, R5, R6. The codec is the standard "schema from type hints" shape and adds no dependency. The cost: a wire name is now a contract; renaming one is a version change. |
| D6 | **A version difference refuses the whole link in v1.** The tab says "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`" and offers no read-only access. Read-only across versions is a later variant behind the handshake. | Accepted | Agent, owner's delegation | Evidence R6. This narrows the charter's Scenario 4 (§6.2); it is stated here because the owner reads it there. |

<!-- The labels above qualify evidence and attribution in the prose; they are not implementation states. -->

## 2a. Constitution check (a default decision only)

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | D3: a forced command is enforced by `sshd`, and R2 proved it refuses a shell, a forward and a terminal. D5: a contract test per root type and a hash of wire names. The "no listener" test of EPIC-038 and AC5 stay. |
| P2 Verify, don't restate | ✅ | Every figure is R1–R6 or the owner's run (§3.8) at a named commit; the VPS figures are the owner's own run, not an extrapolation of the loopback ones. The bridge's start time and the Windows agent are acceptance items, not claims ([EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md)). |
| P3 A copy drifts | ✅ | D1: one gate (`IHostControl` and `HostCommandProcessor`), one pure assessment used by both tabs, a confirmation judged only on the host. D5: one codec, not 550 hand-written lines. |
| P4 Green proves only what was tested | ✅ | The risky points were run on the owner's real machine (R2, R3 on Windows against the VPS), not only in tests. The agent path is recorded as untested (§3.8) and joins 047D as an acceptance item rather than as a pass. |
| P5 Apply before you invent | ✅ | The repository's own `bot show` pattern (read the store's files), its `DirectoryHostControl`, its `health.json` writer. OpenSSH's forced command. The "schema from type hints" codec. Request ids and subscribe as in Home Assistant's WebSocket API (DERISK sources). |
| P6 Fix the mechanism | ✅ | D1 cuts at the doors, so every query and event goes through the one interface, not through a Bots-specific adapter. The doors themselves are fixed first, in EPIC-048. |
| P7 Seam now, variant later | ✅ | One transport and one host today; the transport seam, the host picker and the later variants (Unix socket, VPN, TLS) are named and not built. |
| P8 Ratchets only fall | ✅ | EPIC-038's "no port" decision and test are kept; no guard is loosened. |
| P9 Decide alone | ✅ | Decided under the owner's delegation. The one item that needs the owner is named in D2 (the socket variant) and is not built. |
| P10 Pyramid and units | ✅ | Conclusion first in the title and in each decision; figures carry ms, bytes, lines, counts. |
| P11 Prompt-grade artifacts | ✅ | Each decision names the evidence and the child that delivers it (§5). |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | The record edits no code and no requirements file. The host's write of a facts file (D4) changes no trading rule, order or limit and holds no key; it is its own reviewed child. The bridge is a new process and no Engine file changes (charter G8). No dependency enters with this record (the SSH library has its own record). The forced-command key is an operator step, undone by deleting its line from `authorized_keys`. |

## 3. Alternatives considered

- **The Bots screen only (a port of the screen).** Lost: it would hold a second copy of the screen's reads; every other screen would need its own link (P6).
- **The Engine's IPC or WebSocket port (charter G8).** Lost: it needs an Engine change and a listening port, and no second consumer exists (P7).
- **A listening Unix socket (0600) on the host, dialled through `dial-stdio`.** Deferred: it needs a listener in the running host and the owner's decision. The file-reading bridge needs none and meets AC2 with a factor of about 30 to spare.
- **A TLS endpoint, or a VPN interface.** Lost for v1: both open or add a network path to the trading host, against EPIC-036F D3. They stay variants behind the transport seam.
- **The bridge asks the exchange itself for the exchange facts.** Lost: it adds REST weight on the account and IP the bots use, and the bridge would hold the host's keys (D4).
- **The host computes the whole detail.** Lost: R1 §1.5, a keystroke would wait for an SSH round trip.
- **Hand-written wire forms.** Lost: about 550 lines for 45 records and 225 fields against about 140 reflective lines and a contract test per root (R4).
- **A hash of Python module paths for the handshake.** Lost: moving a class would refuse every desk with the wire unchanged (R6).

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | A Unix socket in `state/` (0600) beside the bridge, if the ~1 s command latency or the facts file prove insufficient. It reverses EPIC-038's "no socket" in spirit. Not built; asked only if a measurement demands it. | A later variant; nothing in EPIC-047 | 2026-10-24 |

## 5. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-048B](../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md), [EPIC-047E](incomplete/EPIC-047E_the_vps_bots_tab.md) | Not started | Not yet verified |
| D2 | [EPIC-047C](incomplete/EPIC-047C_the_bridge_behind_a_forced_command.md), [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) | Not started | Not yet verified |
| D3 | [EPIC-047C](incomplete/EPIC-047C_the_bridge_behind_a_forced_command.md), [EPIC-047G](incomplete/EPIC-047G_the_runbook_for_the_vps_link.md) | Not started | Not yet verified |
| D4 | [EPIC-047B](incomplete/EPIC-047B_the_host_writes_its_in_memory_facts_to_a_file.md) | Not started | Not yet verified |
| D5 | [EPIC-047A](incomplete/EPIC-047A_the_wire_codec_and_the_version_handshake.md) | Not started | Not yet verified |
| D6 | [EPIC-047A](incomplete/EPIC-047A_the_wire_codec_and_the_version_handshake.md), [EPIC-047E](incomplete/EPIC-047E_the_vps_bots_tab.md) | Not started | Not yet verified |
