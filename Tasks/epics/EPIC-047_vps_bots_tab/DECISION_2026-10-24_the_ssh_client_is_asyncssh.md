# ADR — The desktop reaches the VPS through the Python library `asyncssh`, with `paramiko` as the fallback

**Epic:** [EPIC-047](README.md)
**Date:** 2026-10-24
**Status:** Accepted
**Decided by:** the owner's delegation of 2026-10-24, through the coordinating session: *"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"* (translated: "decide them for me, consistent with the whole Constitution"). Settled as G1 of the [charter](CHARTER.md) §4. The owner's preference, stated in the request, was a Python library for portability (charter §2.1). The Constitution check is §2a. The owner may veto the row before the dependency is merged (D2).
**Supersedes / superseded by (optional):** none. Read with [the remote link record](DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | measured in [`DERISK.md`](DERISK.md) R3 (loopback at `5ddbd68`; the owner's Windows run against the VPS, 2026-10-24, §3.8) |
| 🤖 Agent decision | delegated by the owner and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context

The desktop (Windows) starts the bridge on the VPS over SSH and talks to it on stdin and stdout. It can drive the system `ssh` program, or a Python SSH library inside its own process.

**Established facts:**

- ✅ On the owner's Windows 11 (Python 3.14.6, asyncssh 2.24.1, paramiko 5.1.0) against the VPS over the Internet (§3.8): key-file login, host-key pinning, the stdio round trip and the "no TCP listener opened" check **pass for all three clients**. Ready: asyncssh 534 ms, paramiko 503 ms, system `ssh` 657 ms. Round trip p50 / p95: asyncssh 25.6 / 65.4 ms, paramiko 25.3 / 32.7 ms, system `ssh` 27.9 / 31.7 ms. The real numbers do not separate the libraries.
- ✅ **The agent path is untested.** Both libraries failed the agent check (`PermissionDenied`, `SSHException`) because no agent held the key on the owner's machine; the run says nothing about Pageant or the Windows OpenSSH agent. On loopback, both libraries and the system `ssh` logged in through `ssh-agent` with no key file named (§3.3).
- ✅ **Reconnect after an abrupt cut took 1909 ms** on the real link (asyncssh), against 132–423 ms on loopback. The bridge's own imports take 258–269 ms of its ~340 ms start (§3.3).
- ✅ On loopback, asyncssh notices a cut at once and raises typed exceptions (`HostKeyNotVerifiable`, `PermissionDenied`); the system `ssh` reports exit 255 and text on stderr, and needs an agent for an encrypted key under `BatchMode` (§3.3).
- ✅ Two traps (§3.3): `asyncssh.connect(client_keys=None)` passed explicitly **turns key login off** (`PermissionDenied`), while leaving the argument out lets asyncssh ask the agent and read `~/.ssh`; and a blocking call in the client's event loop (`subprocess.Popen.wait`) inflated every event latency to p95 3.0 s until the wait moved to `asyncio.to_thread`.
- ✅ A1 ("the owner has an SSH key") was false until the owner installed one on 2026-10-24; it was installed for root (§3.4, §3.8).
- ✅ The repository's lock already carries `websockets==17.2` and, for Linux only, `cryptography==50.0.2` (`requirements.lock`); no SSH library is locked. `requirements-headless.txt` names the runtime dependencies of a host with no display.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **G1. A Python SSH library, `asyncssh` first, `paramiko` as the fallback.** Not the system `ssh` program. | Accepted | Agent, owner's delegation | Portability: the same behaviour on every OS, the owner's preference. P1: errors are typed exceptions, not text parsed from a child process's stderr. Testable in process. It runs on the same asyncio model as `websockets`. |
| D2 | **The dependency, as the change it will be.** [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md)'s pull request adds `asyncssh` to `requirements.txt`, regenerates `requirements.lock` with the command in the lock's own header (`uv pip compile requirements.txt --universal --python-version 3.12 -o requirements.lock`), pins the version that CI resolves (the run measured 2.24.1), and names the dependency in the pull request body so the owner can veto before merge. The expected transitive effect is that `cryptography`, locked today for Linux only, becomes locked for Windows too; 047D reads the compile's diff and states it. **`requirements-headless.txt` stays unchanged**: the bridge on the host imports no SSH library, since `sshd` is its transport. **This record edits no requirements file.** | Accepted | Agent, owner's delegation | ONBOARDING §7 lists "modify dependencies" as an approval: the owner's delegation of G1 is that approval, and 047D's body is the veto point. If the owner vetoes, G1 returns to the system `ssh` with D3's items as open work. |
| D3 | **Acceptance items the evidence moved to the transport child.** (a) **Agent login on Windows**, through Pageant and through the OpenSSH agent service, tested on the owner's machine; (b) a test that a profile with no key file never passes `client_keys=None` to `asyncssh.connect` (the trap of §1); (c) **reconnect after an abrupt cut in under 2 s** on the real link, with the slim bridge entry point (it imports only the wire layer) in scope; (d) the SSH loop runs on its own thread with no blocking call inside it (`async-ui-action-rule.md`). | Accepted | Agent, owner's delegation | The 1909 ms measured is under the target by only 91 ms, so the slim entry point is part of the target and not an extra. |
| D4 | **Host keys are always pinned.** The client passes `known_hosts` and never turns verification off. A wrong key is refused with a typed error and a sentence naming the host. The profile stores a host, a port, a user, the protocol and a reference to a key file or the agent; **never a password, a passphrase or a key**. | Accepted | Agent, owner's delegation | Evidence: the wrong-pinned-key check passed for both libraries on the real link. The charter's "no secret on disk in the app" (§5.1) holds. The cost: first use needs the host's key in `known_hosts` (the runbook's first step). |
| D5 | **The fallback rule.** `paramiko` becomes the choice only if `asyncssh` fails D3(a) on Windows while `paramiko` passes it. If both fail it, G1 is reopened with the system `ssh` as the candidate. | Accepted | Agent, owner's delegation | The decision rule of DERISK §3.4, kept. No code for `paramiko` is written before it is needed (P7). |

<!-- The labels above qualify evidence and attribution in the prose; they are not implementation states. -->

## 2a. Constitution check (a default decision only)

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | D1: typed exceptions instead of parsed stderr. D3(b): a test holds the `client_keys=None` trap. D4: pinning is a library argument, tested by the wrong-key refusal. |
| P2 Verify, don't restate | ✅ | The numbers are the owner's own run on the real link (§3.8) with the loopback ones kept apart. What was not run (the agent) is recorded as untested and made an acceptance item. The version is read from the lock at the time of the change, not copied from here. |
| P3 A copy drifts | ✅ | D2: the dependency is named once, in `requirements.txt`, and locked once, in `requirements.lock`, by the repository's own compile command. |
| P4 Green proves only what was tested | ✅ | All three clients passed on the real VPS; the agent path did not run, so it is not claimed (D3a). The reconnect figure is the real link's, not loopback's. |
| P5 Apply before you invent | ✅ | A vetted library, not a hand-written SSH client; the order of the Constitution is Stdlib then Battle-Tested Industry Standards, and the stdlib has no SSH client. `paramiko` is the established alternative and is the named fallback. |
| P6 Fix the mechanism | ✅ | Typed errors fix the mechanism that makes a subprocess hard to test; the SSH loop gets its own thread instead of a patch around a blocking call. |
| P7 Seam now, variant later | ✅ | The library sits behind the transport seam (the remote link record, D2), so the fallback or the system `ssh` is a different adapter, written only if needed. |
| P8 Ratchets only fall | ✅ | No guard is loosened. A dependency guard or an SBOM check, if the repository has one, runs on 047D's lock change. |
| P9 Decide alone | ✅ | Decided under the owner's delegation; the owner's veto point is named (D2). |
| P10 Pyramid and units | ✅ | Conclusion first in the title; times carry ms. |
| P11 Prompt-grade artifacts | ✅ | Each decision names the acceptance item or file that holds it. |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | **This record adds no dependency and edits no requirements file.** The dependency is a later, separate, reviewed change that names itself (D2); reverting is deleting one requirement line and re-compiling. No real-money behaviour, setting, Engine file, user data or secret is touched; D4 keeps every secret out of the app. The owner's delegation of G1 stands in for the approval ONBOARDING §7 asks of a dependency; the owner may veto before 047D merges. |

## 3. Alternatives considered

- **The system OpenSSH client (`ssh`) through a subprocess.** Lost: errors arrive as exit 255 and stderr text (not typed, P1); a passphrase-protected key needs an agent under `BatchMode`; a child process is harder to test in process. It performs as well on the real link (p50 27.9 ms) and needs no dependency, so it is the fallback if D2 is vetoed.
- **`paramiko` first.** Lost narrowly: the real numbers are equal (p50 25.3 ms against 25.6 ms) and both give typed errors. `asyncssh` shares the asyncio model of `websockets`, which the link already uses; `paramiko` is threaded and blocking, which the SSH loop would have to wrap. It stays as the named fallback (D5).
- **A hand-written SSH client.** Lost: P5, and a security-sensitive protocol.
- **A VPN or TLS endpoint instead of SSH.** Lost for v1: it opens or adds a network path (the remote link record, §3).

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Does the Windows agent (Pageant, the OpenSSH agent service) log in through `asyncssh`? Not an owner decision: a measurement on the owner's machine, with the key loaded into the agent. | The acceptance of [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md); it can change D5 | 2026-10-24 |

## 5. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) | Not started | Not yet verified |
| D2 | [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) | Not started | Not yet verified; no requirements file edited by this record |
| D3 | [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md), with the slim entry point in [EPIC-047C](incomplete/EPIC-047C_the_bridge_behind_a_forced_command.md) | Not started | Not yet verified |
| D4 | [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) | Not started | Not yet verified |
| D5 | [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) | Not applicable until D3(a) fails | Not applicable |
