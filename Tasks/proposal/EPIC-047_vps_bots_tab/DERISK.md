# De-risk — EPIC-047 VPS Bots tab

| Field | Value |
|-------|-------|
| Document type | De-risk (step 3): throwaway experiments that confirm or overturn the provisional decisions |
| Epic | EPIC-047 — a desktop tab that shows and controls the bots on the VPS host |
| Version | 0.2 (Draft) |
| Status | R1, R4, R5, R6, R7 measured; R2 and R3 proved on localhost; the owner's first run (2026-10-24) found **A1 false** (no SSH key yet); waiting for the re-run after the key setup of §R3.4 |
| Inputs | `CHARTER.md` v0.4 (§4 G1–G9, §5.2 A6–A7) · `DISCOVER.md` v0.2 (§8 R1–R7) · code at `claude/dazzling-feynman-n23hrz` 5ddbd68 · Engine at the `engine.ref` pin f4ef582 |
| Next step | The owner runs §R3.4; then the decision records for G1, G6, G7 and G9, with the amendments of §9 |

**Revision history**

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 2026-10-24 | R1–R7, A6, A7; the owner's script for R2 and R3 |
| 0.2 | 2026-10-24 | The owner's first run: A1 is false (password login, no key); the key setup joins §R3.4; the script catches every check's error and goes on, skips the key-file checks without a key file, and checks `known_hosts` first |

**How to read this document.** One section per experiment: the question, what was run, the measured result with its raw evidence, the verdict (*confirmed*, *overturned* or *inconclusive*) and what the verdict does to G1, G6, G7 or G9. §8 answers A6 and A7; §9 lists the decisions this evidence asks to change. Code excerpts are from throwaway spikes kept outside the repository; nothing under `src/`, `tests/`, `scripts/`, the requirements files or the configuration changed. `file:line` citations are at 5ddbd68.

---

## 0. Summary

| ID | Question (short) | Verdict | Effect |
|----|------------------|---------|--------|
| R1 | Can the Bots tab's detail come entirely through a dispatcher-shaped seam? | **Confirmed**, with an amendment | G6 holds for *facts*; the pure judging stays on the desktop (§1.5). Seam = 6 queries, 2 of them new |
| R2 | Can the desk reach the host with the host listening on no socket? | **Confirmed on localhost**; owner's run pending | G7 holds only for a **file-reading bridge** (the `bot show` pattern), not for Docker's literal shape, which bridges to a listening Unix socket (§2.5) |
| R3 | `asyncssh` vs `paramiko` vs system `ssh`: key file, agent, host-key pinning, reconnect | **Inconclusive** until the owner's Windows run; on Linux all three pass every check | G1 unchanged: `asyncssh` first; one trap recorded (§3.3) |
| R4 | Wire forms for the ~15 types: hand-write or generate? | **Measured**: 45 records, 225 fields, 14 enums, 3 tagged unions behind the 15 roots | Generate the wire forms (one reflective codec, ~140 lines) and keep files' codecs hand-written (§4.5) |
| R5 | Change-to-desk latency ≤ 5 s; no missed change after a reconnect | **Confirmed**: p95 ≤ 100 ms (poll-bound), 6 of 6 runs converge after a forced cut | AC2 met with margin; a desk heartbeat is needed for half-open links (§5.4) |
| R6 | Version handshake detects a mismatch | **Confirmed**: refused in words, exit 3 | Hash wire *names*, not Python module paths; Scenario 4's "read-only on mismatch" needs a decision (§6.4) |
| R7 | Size of the "UI around the doors" debt on every screen | **Measured**: 215 imports in 82 files over 18 screen areas; 30 functions take the container | G9's baseline; two allowlist questions (§7.4) |
| A6 | Every Bots-screen query can be asynchronous | **Holds**, with 1 query and 4 non-query reads to move off the UI thread (§8.1) | — |
| A1 | The owner has an SSH key that logs in to the VPS | **False** (owner's run, 2026-10-24): the owner logs in with a password and has no key | The epic's runbook needs a key-setup step (§R3.4); D6 |
| A7 | The Bots screen can reach the application only through the doors | **Likely true**; the 45 bypass imports of `bots/ui/bots_screen` are listed (§8.2) | — |

---

## Setup common to R2, R3, R5 and R6

| Item | Value |
|------|-------|
| Machine | the session's Linux container, Ubuntu 24.04.5 LTS, Python 3.12 |
| SSH server | OpenSSH 9.6p1 `sshd` on `127.0.0.1:2222`, key login only, an account `sew` standing for the VPS's service account |
| Client libraries | `asyncssh` 2.24.1 and `paramiko` 5.1.0 in a throwaway virtual environment; system `ssh` OpenSSH 9.6p1 |
| Host side | `bridge_host.py`, run by `sshd` as `sew` with the app's own interpreter, so it imports the real `BotChangedEvent` and the Engine's `MemoryEventBus` |
| Limits | loopback only: every transport number is a **lower bound**; the VPS round trip, the Windows agents and Pageant are not reachable from here (R2 and R3 owner run, §R3.4) |

The bridge's protocol, newline-delimited JSON on stdin and stdout:

```text
host -> {"type":"hello","protocol":"sew.bridge/1","app_version":"0.1.0+5ddbd68","contract_hash":"19a2873d5abdc6a3"}
desk -> {"type":"hello", ...same keys...}          a mismatch -> {"type":"refused","differs":[...]} and exit 3
host -> {"type":"welcome"}
desk -> {"id":7,"call":"subscribe"}                 every call carries an id, echoed in its result
host -> {"id":7,"ok":true,"data":{"seq":0}}
host -> {"type":"event","seq":1,"name":"BotChangedEvent","data":{"bot_id":"bot003","removed":false,"record":{...}}}
```

---

## R1 — The Bots tab's detail through one dispatcher-shaped seam

### 1.1 Question
Can the Bots tab render a bot's detail from read models that all come through a dispatcher-shaped interface, without changing what it shows? Which methods would that seam need, derived from `BotsDependencies`?

### 1.2 What was run
A pytest module in scratch (`test_r1_remote_detail.py`, 228 lines). A *host side* answers six queries with real contract types; a `WireDispatcher(ICommandDispatcher)` sends each query by **type name**, encodes it with the reflective codec of R4, sends the JSON text to the host side, and decodes the JSON result. The real `bot_detail.py` → `detail_for` then runs on what came back, and the result is shown by the real `BotsView` (offscreen).

```python
RESULT_TYPES = {ListBotsQuery: BotList, GetPlannerMarketQuery: PlannerMarket,
                GetExchangeFactsQuery: VenueSnapshot, GetPlanRiskFactsQuery: PlanRiskRead,
                GetBotRunFactsQuery: RunFacts, GetConnectionReadQuery: ConnectionRead}
BY_NAME = {q.__name__: q for q in RESULT_TYPES}   # the wire's allowlist

class WireDispatcher(ICommandDispatcher):
    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        request = json.dumps({"id": n, "query": handler_class.__name__,
                              "input": wire.encode(input_dto, handler_class)})
        reply = json.loads(host_serve(request))
        return wire.decode(reply["result"], RESULT_TYPES[handler_class])

def test_the_detail_through_the_wire_equals_the_detail_in_process() -> None:
    through_wire = detail_through(WireDispatcher())
    assert through_wire == detail_through(LocalDispatcher())
    assert "manual:trade-tab" in through_wire.readiness.message()   # the host's lease holder
```

The bot is the Futures draft of `test_the_plan_says_what_the_stop_and_the_take_profit_are_worth.py` (BNBUSDT, 730–750, 10 grids, 200 at 2×, stop 721, take profit 757); the host side's `RunFacts` names a lease holder only the host knows.

### 1.3 Result

```text
test_r1_remote_detail.py::test_the_detail_through_the_wire_equals_the_detail_in_process PASSED
R1: 6 queries, 663 bytes on the wire, 11.8 ms with encode+decode
test_r1_remote_detail.py::test_the_real_view_shows_the_remote_detail PASSED
2 passed in 0.97s
```

- The `BotDetail` built from wire-borne reads **equals** the one built in process (frozen dataclass equality over facts, verdicts, checks, availability, overlay, readiness and ladder).
- The real view shows the Plan's "loss at stop" row, `-4.13% of capital`, computed from the wire-borne reads.
- 663 bytes for one bot's six reads; 11.8 ms on this machine for encode and decode.

**The seam the screen needs**, field by field of `bots_dependencies.py` → `BotsDependencies`:

| Field | Today | Over the seam | Kind |
|-------|-------|---------------|------|
| `commands` | `ListBotsQuery`, `GetPlannerMarketQuery`, `GetExchangeFactsQuery`, `GetPlanRiskFactsQuery`, `GetVenueConnectionQuery`, `GetBotFillsQuery`, `ExportBotPlanQuery`, and every command | the same queries; commands through `IHostControl` (G6) | existing |
| `run_facts: BotRunFactsReader` | **synchronous**, on the UI thread, against the desktop's own trading ports and budget caps (`selected_bot.py:196`) | `GetBotRunFactsQuery(bot_id, config)` → `RunFacts`; the host computes the occupancy too (it knows its own bots and symbol leases) | **new query** |
| `contexts: IVenueContexts` | venue choices read each venue's **stored key** on the UI thread (`venue_choice.py:95`); `venue_filters` reads each venue's metadata cache (`bots_dependencies.py:175`) | `GetVenueChoicesQuery` → each venue's connection state (*a key is saved*, never the key); the filters ride in `PlannerMarket.terms`, which already carries tick and step sizes | **new query** |
| `venues: IVenueTradingPorts` | only feeds `BotRunFactsReader` | gone from the screen | removed |
| Connect step | builds `ConnectionRead` in the UI from `VenueAccountSnapshot \| ConnectFailure` (`connect_step.py:267`) | unchanged query; the composition moves to the application layer or stays a pure UI function | existing |
| `feeds`, `ticks`, `symbols`, `workbench_ports` | public market data, the desktop's own candle store, the backtest | stay local (charter: the backtest runs on the desktop) | local |
| `kinds: IBotKindCatalog` | the kinds' judges and editors | stay local: code, not data; R6 guarantees the same code on both sides | local |
| `notifier`, `consent`, `instance`, `display_timezone`, `threads` | UI concerns | stay local | allowlist |
| bus: `BotChangedEvent`, `ArmedStrategyChangedEvent`; `BotLogFeed` | in-process bus and a log handler | events over the bridge (R5); the log lines later (G4) | stream |

### 1.4 Verdict
**Confirmed, with an amendment.** The detail renders identically from six dispatcher reads that crossed a wire. The seam is the existing dispatcher plus two new queries (`GetBotRunFactsQuery`, `GetVenueChoicesQuery`) and the event stream.

### 1.5 What it does to G6
G6 says *"the screen receives read models from queries and does not compute readiness itself"*. R1 shows that the half about **facts** holds, and that the half about **computation** should not be read as "the host computes the detail":

- `detail_for` is a pure function of nine inputs; seven are host facts (they cross the wire), two are local (`now`, the unsaved edits).
- The Plan re-judges on every edit, 150 ms after the last keystroke (`presenter_pacing.py:23`, `REJUDGE_MS`). A host-computed detail would turn each edit into an SSH round trip.

**Recommended wording for G6:** *every host fact reaches the screen through a query or a bus event; the pure assessment over those facts (`detail_for`, `assess_readiness`, the kinds' judges) leaves `ui/` for the application layer as a pure read-model builder, and runs on the desktop.* G9 then moves the computation out of the presenter without moving it to the host.

---

## R2 — A link to the host with the host listening on no socket

### 2.1 Question
Can the desk reach the running host without the host listening on any socket, using a command run over SSH that speaks on stdin and stdout?

### 2.2 What was run
`ssh … bridge_host.py` with each client library (§R3). While a bridge was serving, `ss -Hlpn` listed every listening socket and filtered those owned by the bridge's pid. A second key was then restricted in `authorized_keys` to run only the bridge (OpenSSH *forced command*):

```text
restrict,command="cd /opt/sew-spike && … exec …/python bridge_host.py" ssh-ed25519 AAAA…
```

### 2.3 Result

```text
bridge pids: ['3531'] | listening sockets owned by them: []
all listeners: [… 'tcp LISTEN 0 128 127.0.0.1:2222', …]          # sshd only; the rest belong to the container
```

| Check | Result |
|-------|--------|
| Sockets the bridge listens on (TCP, UDP, Unix) | **none**; the only new listener on the path is the `sshd` the VPS already runs |
| The restricted key asks for `whoami; cat /etc/passwd` | it gets the bridge's `hello` instead: the command the key may run is fixed by the host |
| The restricted key asks for a port forward (`-L 9999:127.0.0.1:2222`) | `channel 1: open failed: administratively prohibited`; the server logs `refused local port forward` |
| The restricted key asks for a terminal (`-tt`) | `PTY allocation request failed on channel 0` |
| Bridges left on the host 0.5 s after the TCP connection was aborted | **0** (6 of 6 runs) |
| Bridges left after a *half-open* cut (the client frozen with `SIGSTOP`, no FIN) | **1 after 10 s** without a heartbeat; **0** with the bridge's idle watchdog at 6 s (§5.4) |

### 2.4 Verdict
**Confirmed on localhost.** A stdio bridge started by `sshd` listens on nothing. The owner's run (§R3.4) proves the same round trip against the VPS; its `the echo opened no TCP listener` check compares `ss -Hltn` before and during the session.

### 2.5 What it does to G7
G7 names "the Docker `dial-stdio` pattern". Docker's `dial-stdio` copies stdio to the daemon's **listening Unix socket**. Here the bridge is a *second process* on the host, as `M bot …` is, and the running host has no socket to dial. The experiment confirms G7 only in this shape:

| Need | How a second process gets it without a socket | Evidence |
|------|-----------------------------------------------|----------|
| The bots and their progress | read the store's files, as the read-only `bot list` and `bot show` do | `ReadOnlyBotStore`; the R5 bridge |
| Changes | one `BotChangedEvent` per write to a bot's file (the store's own rule, `bot_changed_event.py`), detected by polling the directory | R5: 52 ms p50 |
| Commands | `DirectoryHostControl`, exactly as the CLI: the host's gate, audit, replay and expiry checks stay the one door | Discover §3.2; the host polls every 1 s, so a command adds up to ~1 s |
| Facts only the running host holds in memory (symbol leases, enabled venues, budget caps, the exchange's answers) | **not reachable** today. Either the host writes them to a file, as it already writes `state/health.json` every 10 s (`health_snapshot.py`, `HEALTH_INTERVAL_SECONDS`), or the bridge asks the exchange itself | gap, see §9 item 2 |

Two consequences:
- **Identity.** The bridge must run as `sew`. Today an operator uses `sudo -u sew` (`deploy/linux/sew-profile.sh` → `_sew_as_service`), which a non-interactive SSH session cannot answer. A key restricted to the bridge in `sew`'s `authorized_keys` (above) gives the desk exactly one capability, no shell and no forwarding.
- **Exchange load.** A bridge that answers `GetExchangeFactsQuery` or `GetVenueConnectionQuery` itself makes REST calls with the host's keys, adding request weight on the same account and IP as the running bots. Host-published facts avoid that.

---

## R3 — `asyncssh` vs `paramiko` vs system `ssh`

### 3.1 Question
On the owner's Windows: login with a key file and with an agent (Pageant, the Windows OpenSSH agent), host-key pinning, reconnect. Which client should the desktop use?

### 3.2 What was run on localhost
The same experiment with each client, three runs each: connect, start the bridge, handshake, 200 pings, subscribe then snapshot, 120 writes by a stand-in host, an abrupt cut after 2 s, a reconnect and resynchronisation, a mismatch, a wrong pinned host key, and a login through `ssh-agent` with no key file named.

```python
# asyncssh (excerpt)
conn = await asyncssh.connect(HOST, PORT, username=USER, known_hosts=KNOWN_HOSTS,
                              client_keys=[KEY], agent_path=None)
proc = await conn.create_process(BRIDGE, encoding="utf-8")
...
link.conn.abort()                 # the cut: no goodbye

# paramiko (excerpt)
client = paramiko.SSHClient()
client.load_host_keys(KNOWN_HOSTS)
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(HOST, PORT, USER, key_filename=KEY, allow_agent=False, look_for_keys=False)
channel = client.get_transport().open_session(); channel.exec_command(BRIDGE)
...
client.get_transport().sock.shutdown(socket.SHUT_RDWR)   # the cut
```

### 3.3 Result (loopback; three runs each)

| Measure | asyncssh 2.24.1 | paramiko 5.1.0 | system ssh 9.6p1 |
|---------|-----------------|----------------|------------------|
| TCP + SSH + key login | 30–34 ms | 60–63 ms | (in the next row) |
| Desk ready (login + bridge started + handshake) | 580–630 ms | 597–665 ms | 505–725 ms |
| of which the bridge's own imports (app + Engine) | 258–269 ms | same bridge | same bridge |
| Ping round trip, 200 samples | p50 0.27–0.33 ms, p95 0.45–0.53 ms | p50 0.20–0.22 ms, p95 0.30–0.35 ms | p50 0.12 ms, p95 0.16 ms |
| Cut noticed by the desk | at once (`abort`) | 0.5–1.8 ms | — |
| Reconnect to resynchronised view | 367–423 ms | 380–524 ms | — |
| Wrong pinned host key | refused, `HostKeyNotVerifiable` | refused, `BadHostKeyException` | — |
| Login through the agent, no key file | ok | ok | ok |
| Encrypted key with a passphrase | ok | ok | needs the agent (`BatchMode`) |
| Errors are typed exceptions | yes | yes | no: exit 255 and stderr text |

Raw evidence, asyncssh run 1:

```json
{
 "library": "asyncssh 2.24.1",
 "first_connect": {"connect_ms": 33.5, "bridge_hello_ms": 340.5, "ready_ms": 598.3},
 "bridge_import_ms": 258.4,
 "ping_rtt": "n=200 p50=0.33 p95=0.53 max=0.98 ms",
 "bridges_on_host_0.5s_after_cut": 0,
 "reconnect_to_resynced_ms": 406.9,
 "final_view_equals_host": true,
 "bots": 10,
 "events_applied_after_reconnect": 63,
 "events_skipped_as_in_snapshot": 0,
 "change_to_desk_latency": "n=101 p50=51.36 p95=97.52 max=101.11 ms",
 "bridges_on_host_after_clean_close": 0,
 "mismatch": {"type": "refused", "differs": ["contract_hash"], "exit_status": 3},
 "wrong_host_key": "refused: HostKeyNotVerifiable",
 "agent_only_login": "ok"
}
```

paramiko run 1:

```json
{
 "library": "paramiko 5.1.0",
 "first_connect": {"connect_ms": 60.8, "bridge_hello_ms": 340.4, "ready_ms": 604.4},
 "ping_rtt": "n=200 p50=0.22 p95=0.33 max=0.62 ms",
 "cut_noticed_ms": 1.8,
 "bridges_on_host_0.5s_after_cut": 0,
 "reconnect_to_resynced_ms": 432.2,
 "final_view_equals_host": true,
 "events_applied_after_reconnect": 62,
 "change_to_desk_latency": "n=101 p50=51.17 p95=81.27 max=100.96 ms",
 "bridges_on_host_after_clean_close": 0,
 "mismatch": {"type": "refused", "differs": ["contract_hash"], "exit_status": 3},
 "wrong_host_key": "refused: BadHostKeyException",
 "agent_only_login": "ok"
}
```

**Traps found.**
- `asyncssh.connect(client_keys=None)` passed explicitly **turns key login off** (`PermissionDenied`); leaving the argument out lets asyncssh ask the agent and read `~/.ssh`. A profile that maps "no key file" to `None` would lock the owner out.
- In the client's event loop, a blocking call (`subprocess.Popen.wait`) stalled the reader and inflated every event latency to p95 3.0 s, max 3.2 s, until the wait moved to `asyncio.to_thread`. The desktop's SSH loop must run on its own thread with no blocking call inside it (`async-ui-action-rule.md`).
- The bridge's start time is dominated by imports (258–269 ms of ~340 ms). A slim bridge entry point that imports only the wire layer keeps reconnects short.

### 3.4 What the owner runs on Windows (R2 and R3 on the real machines)

**The owner's first run (2026-10-24, Windows 11, Python 3.14.6, asyncssh 2.24.1, paramiko 5.1.0).** The key-file check failed with `FileNotFoundError` and the agent check with `PermissionDenied`: the owner logs in to the VPS with a password and has no key, so **assumption A1 is false**. Version 0.1 of the script then stopped on an uncaught `FileNotFoundError` in the wrong-pin check, before the paramiko and system `ssh` checks; version 0.2 (§R3.5) catches every check's error, reports it and goes on.

**Prerequisites.** Python 3.12 or later on the desktop (3.14.6 works); the VPS's host key already in `%USERPROFILE%\.ssh\known_hosts` (log in once with `ssh <login>@<vps>` and accept the key); a key that logs in, set up once as below.

**Key setup, once** (PowerShell, on the desktop; the passphrase is asked by `ssh-keygen` and never typed on a command line):

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519            # choose a passphrase when asked
# install the public half on the VPS (asks the VPS password one last time)
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | ssh <login>@<vps> "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys"
# the agent, for the agent checks (an administrator PowerShell for the two service lines)
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
ssh-add $env:USERPROFILE\.ssh\id_ed25519
ssh -o BatchMode=yes <login>@<vps> true; $LASTEXITCODE                  # 0: the key logs in with no password
```

Only the `.pub` file leaves the desktop. Turning password login off on the VPS (`PasswordAuthentication no`) is a separate hardening step, out of this experiment's scope; the epic's runbook (D6) carries this key setup as its first step.

**Commands** (PowerShell; the script is in §R3.5; save it as `derisk_r2_r3.py`):

```powershell
py -3.12 -m venv $env:TEMP\sew-derisk
& $env:TEMP\sew-derisk\Scripts\python.exe -m pip install asyncssh paramiko
& $env:TEMP\sew-derisk\Scripts\python.exe -I derisk_r2_r3.py --host <vps> --user <login> --key $env:USERPROFILE\.ssh\id_ed25519
# add --ask-passphrase when the key file has one (typed, not shown, not stored)
```

**Reading the output.** One line per check, `[PASS]`, `[FAIL]` or `[SKIP]`, then `N PASS, M FAIL, K SKIP`; exit code 0 only when nothing failed. A failing check never stops the next one. A `--key` that names no file skips the key-file checks with one `[SKIP]` line. The script prints no key, no passphrase and no secret: library versions, timings and the type name of an error only. It runs a stdlib-only echo program on the VPS (`python3 -c …`) and changes nothing there.

| Line | Pass means | Fail means |
|------|------------|------------|
| `known_hosts holds a pinned key file` | `%USERPROFILE%\.ssh\known_hosts` exists | log in once with `ssh <login>@<vps>` and accept the key |
| `[SKIP] key file … not found` | — | no key yet: do the key setup above, then run again |
| `asyncssh …: login with the key file, host key pinned` | G1's first choice logs in from Windows | read the error type: `PermissionDenied` (key not in `authorized_keys`), `HostKeyNotVerifiable` (host not in `known_hosts`), `KeyImportError` (passphrase: add `--ask-passphrase`) |
| `…: stdio round trip x50` | R2: the link works; the p50 and p95 are the **real** VPS round trip that AC2 adds to R5's 100 ms | the link drops or stalls |
| `…: the echo opened no TCP listener` | R2: `ss -Hltn` on the VPS is the same before and during the session | something listened: report it |
| `…: reconnect after an abrupt cut` | R3: a new session is ready within 5 s | slower than 5 s: report the time |
| `…: login through the SSH agent (no key file named)` | Pageant or the Windows OpenSSH agent works with that library | expected when no agent holds the key; otherwise G1's choice on Windows is in question |
| `…: a wrong pinned host key is refused` | host-key pinning holds | **stop**: the library connected to a host whose key it did not know |
| `system ssh: …` | the system client works too (G1's alternative) | only matters if both libraries fail |

**Decision rule.** G1 stays as decided (`asyncssh` first) if every `asyncssh` line passes, the agent line included. If `asyncssh` fails the agent line and `paramiko` passes it, the fallback becomes the choice. If both fail it, G1 is reopened with the system `ssh` as the candidate.

### 3.5 The script

```python
"""EPIC-047 De-risk R2 + R3: an SSH stdio round trip to the VPS, from the owner's desktop.

Runs a tiny stdlib-only echo program on the VPS over SSH (it opens no socket), with asyncssh,
with paramiko and with the system `ssh`, and prints PASS / FAIL / SKIP per check. Every check
catches its own error, reports it and goes on to the next one. It prints no key, no passphrase
and no secret: only library versions, timings and the *type name* of an error.

  python derisk_r2_r3.py --host <vps> --user <login> [--key <private key file> [--ask-passphrase]] [--port 22]
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import getpass
import json
import os
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

# The program the VPS runs: echo each line with the host's clock; list TCP listeners at start and
# again while the round trip is open, so the output shows the echo itself added none.
REMOTE = r'''
import json, sys, time, subprocess
def listeners():
    try:
        return sorted(subprocess.run(["ss", "-Hltn"], capture_output=True, text=True).stdout.split("\n"))
    except FileNotFoundError:
        return ["ss not installed"]
before = listeners()
print(json.dumps({"hello": "derisk/1", "python": sys.version.split()[0]}), flush=True)
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("call") == "listeners":
        print(json.dumps({"id": msg["id"], "same_as_before": listeners() == before}), flush=True)
    else:
        print(json.dumps({"id": msg["id"], "host_ns": time.time_ns()}), flush=True)
'''
RESULTS: list[tuple[str, str, str]] = []
KNOWN_HOSTS = os.path.expanduser("~/.ssh/known_hosts")


def remote_command(python: str) -> str:
    code = base64.b64encode(REMOTE.encode()).decode()
    return f"exec {python} -c \"import base64;exec(base64.b64decode('{code}'))\""


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(("PASS" if ok else "FAIL", name, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)


def skip(name: str, why: str) -> None:
    RESULTS.append(("SKIP", name, why))
    print(f"[SKIP] {name}: {why}", flush=True)


def failed(name: str, error: BaseException) -> None:
    check(name, False, type(error).__name__)


def stats(values: list[float]) -> str:
    q = statistics.quantiles(values, n=20)
    return f"p50={statistics.median(values):.1f} ms p95={q[18]:.1f} ms"


def fake_known_hosts(host: str, port: int) -> str:
    """A known_hosts that names a key the VPS does not have: a pinned client must refuse it."""
    name = host if port == 22 else f"[{host}]:{port}"
    blob = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + os.urandom(32)  # a random public key
    key = base64.b64encode(blob).decode()
    path = Path(tempfile.mkdtemp()) / "known_hosts"
    path.write_text(f"{name} ssh-ed25519 {key}\n")
    return str(path)


# ---------------------------------------------------------------- asyncssh
async def asyncssh_suite(a: argparse.Namespace, passphrase: str | None) -> None:
    import asyncssh

    lib = f"asyncssh {asyncssh.__version__}"

    async def session(**kw: object) -> tuple[float, list[float], bool]:
        t0 = time.perf_counter()
        async with asyncssh.connect(a.host, a.port, username=a.user, **kw) as conn:
            proc = await conn.create_process(remote_command(a.remote_python), encoding="utf-8")
            json.loads(await proc.stdout.readline())
            ready = (time.perf_counter() - t0) * 1e3
            rtts = []
            for n in range(50):
                t = time.perf_counter()
                proc.stdin.write(json.dumps({"id": n, "call": "ping"}) + "\n")
                assert json.loads(await proc.stdout.readline())["id"] == n
                rtts.append((time.perf_counter() - t) * 1e3)
            proc.stdin.write(json.dumps({"id": 99, "call": "listeners"}) + "\n")
            same = json.loads(await proc.stdout.readline())["same_as_before"]
            conn.abort()  # the cut: no goodbye
            return ready, rtts, same

    pinned = {"known_hosts": KNOWN_HOSTS}
    with_key = {"client_keys": [a.key], "passphrase": passphrase, "agent_path": None}
    if a.key:
        name = f"{lib}: login with the key file, host key pinned"
        try:
            ready, rtts, same = await session(**with_key, **pinned)
            check(name, True, f"ready {ready:.0f} ms")
            check(f"{lib}: stdio round trip x50", max(rtts) < 2000, stats(rtts))
            check(f"{lib}: the echo opened no TCP listener", same)
        except Exception as error:
            failed(name, error)
        name = f"{lib}: reconnect after an abrupt cut"
        try:
            t = time.perf_counter()
            ready2, _, _ = await session(**with_key, **pinned)
            check(name, ready2 < 5000, f"{(time.perf_counter() - t) * 1e3:.0f} ms")
        except Exception as error:
            failed(name, error)
    else:
        skip(f"{lib}: key-file checks", "no key file (see --key)")
    name = f"{lib}: login through the SSH agent (no key file named)"
    try:  # leaving client_keys out lets asyncssh ask the agent: Pageant or the Windows OpenSSH agent
        ready, _, _ = await session(**pinned)
        check(name, True, f"ready {ready:.0f} ms")
    except Exception as error:
        failed(name, error)
    name = f"{lib}: a wrong pinned host key is refused"
    try:  # the host key is checked before any login, so this holds with or without a key
        await session(known_hosts=fake_known_hosts(a.host, a.port), **(with_key if a.key else {}))
        check(name, False, "it connected")
    except asyncssh.HostKeyNotVerifiable as error:
        check(name, True, type(error).__name__)
    except Exception as error:
        failed(name, error)


# ---------------------------------------------------------------- paramiko
def paramiko_suite(a: argparse.Namespace, passphrase: str | None) -> None:
    import paramiko

    lib = f"paramiko {paramiko.__version__}"

    def session(known_hosts: str | None = None, **kw: object) -> tuple[float, list[float], bool]:
        t0 = time.perf_counter()
        client = paramiko.SSHClient()
        if known_hosts:
            client.load_host_keys(known_hosts)
        elif os.path.exists(KNOWN_HOSTS):
            client.load_host_keys(KNOWN_HOSTS)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(a.host, a.port, a.user, look_for_keys=False, timeout=15, **kw)
        try:
            channel = client.get_transport().open_session()
            channel.exec_command(remote_command(a.remote_python))
            out, inp = channel.makefile("r"), channel.makefile_stdin("w")
            json.loads(out.readline())
            ready = (time.perf_counter() - t0) * 1e3
            rtts = []
            for n in range(50):
                t = time.perf_counter()
                inp.write(json.dumps({"id": n, "call": "ping"}) + "\n")
                inp.flush()
                assert json.loads(out.readline())["id"] == n
                rtts.append((time.perf_counter() - t) * 1e3)
            inp.write(json.dumps({"id": 99, "call": "listeners"}) + "\n")
            inp.flush()
            same = json.loads(out.readline())["same_as_before"]
            return ready, rtts, same
        finally:
            client.close()

    if a.key:
        name = f"{lib}: login with the key file, host key pinned"
        try:
            ready, rtts, same = session(key_filename=a.key, passphrase=passphrase, allow_agent=False)
            check(name, True, f"ready {ready:.0f} ms")
            check(f"{lib}: stdio round trip x50", max(rtts) < 2000, stats(rtts))
            check(f"{lib}: the echo opened no TCP listener", same)
        except Exception as error:
            failed(name, error)
    else:
        skip(f"{lib}: key-file checks", "no key file (see --key)")
    name = f"{lib}: login through the SSH agent (no key file named)"
    try:
        ready, _, _ = session(allow_agent=True)
        check(name, True, f"ready {ready:.0f} ms")
    except Exception as error:
        failed(name, error)
    name = f"{lib}: a wrong pinned host key is refused"
    try:  # the host key is checked before any login, so this holds with or without a key
        session(known_hosts=fake_known_hosts(a.host, a.port),
                **({"key_filename": a.key, "passphrase": passphrase} if a.key else {"allow_agent": True}))
        check(name, False, "it connected")
    except paramiko.BadHostKeyException as error:
        check(name, True, type(error).__name__)
    except Exception as error:
        failed(name, error)


# ---------------------------------------------------------------- system ssh
def system_ssh_suite(a: argparse.Namespace) -> None:
    command = ["ssh", "-T", "-o", "BatchMode=yes", "-p", str(a.port)]
    if a.key:
        command += ["-i", a.key]
    name = "system ssh: login and stdio round trip x50"
    t0 = time.perf_counter()
    try:
        proc = subprocess.Popen(command + [f"{a.user}@{a.host}", remote_command(a.remote_python)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, bufsize=1)
    except FileNotFoundError:
        check("system ssh: found on PATH", False)
        return
    try:
        first = proc.stdout.readline()
        if not first:
            check("system ssh: login (BatchMode, key from agent or -i)", False, f"exit {proc.wait()}")
            return
        ready = (time.perf_counter() - t0) * 1e3
        rtts = []
        for n in range(50):
            t = time.perf_counter()
            proc.stdin.write(json.dumps({"id": n, "call": "ping"}) + "\n")
            proc.stdin.flush()
            json.loads(proc.stdout.readline())
            rtts.append((time.perf_counter() - t) * 1e3)
        proc.stdin.close()
        proc.wait()
        check(name, True, f"ready {ready:.0f} ms, {stats(rtts)}")
    except Exception as error:
        proc.kill()
        failed(name, error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--key", help="private key file (optional when an agent holds the key)")
    parser.add_argument("--ask-passphrase", action="store_true", help="the key file has a passphrase")
    parser.add_argument("--remote-python", default="python3")
    a = parser.parse_args()
    check("known_hosts holds a pinned key file", os.path.exists(KNOWN_HOSTS),
          KNOWN_HOSTS if os.path.exists(KNOWN_HOSTS) else f"{KNOWN_HOSTS} missing: run `ssh {a.user}@{a.host}` once")
    if a.key and not os.path.isfile(a.key):
        print(f"[SKIP] key file {a.key} not found: the key-file checks are skipped (DERISK §3.4 makes one)")
        a.key = None
    passphrase = None
    if a.key and a.ask_passphrase:
        passphrase = getpass.getpass("Key passphrase (not shown, not stored): ") or None
    print(f"agent: {'SSH_AUTH_SOCK set' if os.environ.get('SSH_AUTH_SOCK') else 'none in env (Windows: Pageant or the OpenSSH agent service)'}")
    for suite in ("asyncssh", "paramiko", "system ssh"):
        try:
            if suite == "asyncssh":
                asyncio.run(asyncssh_suite(a, passphrase))
            elif suite == "paramiko":
                paramiko_suite(a, passphrase)
            else:
                system_ssh_suite(a)
        except ImportError:
            check(f"{suite}: installed", False, "pip install " + suite)
        except Exception as error:  # a suite never stops the next one
            failed(f"{suite}: suite", error)
    count = {status: sum(1 for r in RESULTS if r[0] == status) for status in ("PASS", "FAIL", "SKIP")}
    print(f"\n{count['PASS']} PASS, {count['FAIL']} FAIL, {count['SKIP']} SKIP")
    return 1 if count["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 3.6 Verdict
**Inconclusive** until the owner's run: on Linux the three clients pass every check and differ by under 0.2 ms per round trip. What decides G1 is the Windows agent and Pageant support, which only the owner's run shows.

### 3.7 What it does to G1
Nothing yet. The loopback evidence favours a library over the system client: typed errors (P1), the cut noticed at once, a passphrase-protected key without an agent. Between the two libraries the numbers do not decide; `asyncssh` stays first for its asyncio model and its documented Pageant and Windows-agent support, recorded with the `client_keys=None` trap.

---

## R4 — Wire forms for the contract types

### 4.1 Question
Hand-write or generate the wire forms of the ~15 types Discover §5 lists, and keep them in step: what does one type cost, and what traps does it hold?

### 4.2 What was run
1. `BotSnapshot` and everything it holds, **hand-written** (`wire_bot_snapshot.py`): encode and decode for `BotSnapshot`, `BotProgress`, `BotOrderLine`, `PnlSummary` and `RecoveryAttempt` — 5 records, 45 fields.
2. The same round trip through a **reflective codec** (`wire_generic.py`) that walks `typing.get_type_hints`: str, int, bool, `Decimal`, `datetime`, `Enum`, `NewType`, PEP 695 `type` aliases, `X | None`, `tuple[X, ...]`, `Mapping[str, str]`, nested dataclasses, and unions of records with a `"$type"` tag.
3. A contract test (`test_wire_bot_snapshot.py`, 10 tests) over both, plus a mutation: one field removed from the hand-written encoder.
4. A probe (`probe_types.py`) that walks the 15 root types and counts what a wire form must cover.

```python
def encode(s: BotSnapshot) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "bot_id": s.bot_id, "name": s.name, "kind": s.kind,
        "venue": s.venue.value, "symbol": s.symbol, "state": s.state.value,
        "created_at": s.created_at.isoformat(), "run_started_at": _when(s.run_started_at),
        "config": dict(s.config),
        "progress": None if s.progress is None else _progress(s.progress),
        ...

def test_every_field_of_every_record_has_a_wire_key() -> None:
    """The drift lock: a field added to a contract type without its wire key fails here."""
    doc = hand.encode(full())
    assert set(doc) - {"schema"} == {f.name for f in dataclasses.fields(BotSnapshot)}
    assert set(doc["progress"]) == {f.name for f in dataclasses.fields(BotProgress)}
    ...

@pytest.mark.parametrize("snapshot", [full(), minimal()], ids=["full", "minimal"])
def test_generic_round_trip(snapshot: BotSnapshot) -> None:
    back = generic.decode(_over_the_wire(generic.encode(snapshot, BotSnapshot)), BotSnapshot)
    assert back == snapshot
    assert type(back.venue) is TradingVenue and type(back.state) is BotLifecycleState
```

### 4.3 Result

```text
test_wire_bot_snapshot.py ..........                                       10 passed in 0.07s
mutation (maker_fee dropped from the encoder):  KeyError: 'maker_fee'      4 failed, 6 passed
```

The probe over the 15 roots (`BotSnapshot`, `BotReadiness`, `ExchangeFacts`, `VenueSnapshot`, `BotCommandResult`, `BotList`, `BotFills`, `PlannerMarket`, `PlanRiskRead`, `VenueAccountSnapshot`, `ConnectFailure`, `RunFacts`, `ConnectionRead`, `HostControlRequest`, `HostControlReply`):

```text
records reached: 45; fields: 225; enums: 14
TRAP NewType (erased on the wire): 1            RecoveryAttempt.code
TRAP PEP 695 `type` alias (resolve .__value__): 2   PlanRiskRead, VenueSnapshot
TRAP union of several records (needs a type tag): 3
    PlanRiskRead: PlanRiskFacts | PlanRiskUnavailable
    VenueSnapshot: ExchangeChecking | ExchangeUnavailable | ExchangeLoaded
    VenueSnapshot: ExchangeChecking | ExchangeUnavailable | FuturesLoaded
```

No `float`, no mapping with non-text keys, no `Literal`, no exception type and no enum that is not a `str` enum was found.

| Measure | Hand-written | Reflective |
|---------|--------------|------------|
| `BotSnapshot` and its 4 nested records (45 fields) | 128 lines (110 of codec): ~2.4 lines per field, each one a place to forget a field | 0 extra lines |
| All 45 records (225 fields) | ~550 lines of codec, by the same rate, plus a field-coverage lock per record | **137 lines in total**, unions and aliases included; R1 used it for six roots unchanged |
| Drift | caught only by a coverage test per record | impossible by construction: the codec reads the dataclass |

**Traps** (each one has a test in the spike):
- **Decimal as text, never as a JSON number**: `0.1 + 0.2` through `float` is not `0.3`; the text keeps trailing zeros (`12.3400`), the exponent form (`1E-8`) and the sign of `-0`.
- **A `str` enum left as text still compares equal** (`TradingVenue.SPOT_TESTNET == "spot_testnet"`): a round-trip test must assert the *type*, or a decoder that forgets the enum passes.
- **Datetimes keep their offset; a naive datetime stays naive**: `isoformat` keeps `+07:00`; nothing converts a naive time to UTC, so a naive field would cross as naive.
- **`Decimal("NaN") != Decimal("NaN")`**: equality-based contract tests cannot cover a NaN.
- **Unions of records need a tag**: three unions; the tag must be a wire name (§6.4), not a Python class name, so a rename does not break the wire.
- **`MappingProxyType`** is not JSON-serialisable; `BotSnapshot.config` must be copied to a `dict`.

### 4.4 Verdict
**Measured.** One type end to end costs ~110 lines hand-written and nothing more with the reflective codec; the ~15 roots are 45 records behind them, not 15.

### 4.5 What it does to G6
G6's cut needs a wire form for every record behind its queries. Recommendation: **one reflective codec** for the link, locked by a round-trip contract test per root type (types asserted, a full and a minimal instance). The hand-written codecs of the files (`bot_record_codec.py`, `host_command_codec.py`) stay as they are, because a stored file must read across versions while the link is same-version by R6's handshake. P5 is kept: the codec applies the standard "schema from type hints" shape, and adds no dependency.

---

## R5 — Freshness over the bridge, and no missed change after a reconnect

### 5.1 Question
Can the host push `BotChangedEvent` to a remote desk within AC2's 5 s, and recover after a reconnect without missing a change?

### 5.2 What was run
`host_writer.py` stands in for `sew-run`: 10 bot files, 120 atomic rewrites 50 ms apart (write a temporary file, then `Path.replace`, as `JsonBotStore` does), each stamped with `written_ns`. The bridge polls the directory every 100 ms; each changed file publishes a real `BotChangedEvent` on the Engine's `MemoryEventBus`; the bridge's subscriber writes it to stdout. The desk applies **subscribe, then snapshot**: events with `seq` at or below the snapshot's `seq` are skipped. After 2 s the TCP connection is aborted; the desk reconnects, subscribes and takes a new snapshot while the writes continue; at the end its view is compared with the files.

```python
class Bridge:
    def __init__(self) -> None:
        self.bus = MemoryEventBus()
        self.bus.on(BotChangedEvent, self._forward)       # the subscriber that feeds the wire

    def watch(self) -> None:                              # stand-in for NotifyingBotStore
        while True:
            time.sleep(POLL_S)
            now = stats()
            for bot_id, stamp in now.items():
                if self._seen.get(bot_id) != stamp:
                    self.bus.emit(BotChangedEvent(bot_id=bot_id))
            ...

async def subscribe_then_snapshot(link: Link, view: View) -> None:
    await link.call("subscribe")
    view.take_snapshot(await link.call("snapshot"))
```

### 5.3 Result

| Measure | asyncssh (3 runs) | paramiko (3 runs) |
|---------|-------------------|-------------------|
| Write on the host → event applied on the desk | p50 51.4–51.7 ms, p95 97.5–100.1 ms, max 101–102 ms | p50 50.7–51.9 ms, p95 81–99 ms, max 100–101 ms |
| of which on the host (write → sent) | p50 51.6 ms, p95 98.7 ms (the 100 ms poll) | same bridge |
| of which on the wire (sent → received) | p50 0.68 ms, p95 1.05 ms | — |
| Desk's view equals the files after cut, reconnect and resync | **true**, 3 of 3 | **true**, 3 of 3 |
| Events applied after the reconnect | 62–63 | 60–63 |

### 5.4 Verdict and effects
**Confirmed.** AC2 (≤ 5 s) holds with a margin of ~4.9 s before the VPS's real round trip (measured by §R3.4) is added. Snapshot-then-subscribe converges every time. Three design inputs:
- **A per-bot revision.** The spike's convergence relies on the snapshot being newer than the events it overtakes. A monotonic revision in each bot's record, applied only when greater, makes the order of a snapshot and an event irrelevant.
- **A desk heartbeat.** A frozen laptop leaves a half-open TCP connection and no FIN: without a heartbeat the bridge stayed alive (1 left after 10 s); with an idle watchdog of 6 s it ended itself (0 left). The desk pings at a third of the watchdog's interval; the watchdog is the bridge's own, so it does not depend on the VPS's `sshd` settings.
- **Polling cost.** One `scandir` every 100 ms on a directory of 10 files; the store already notifies in process, so a host-side "changes" file or an `inotify` watch can replace the poll later behind the same event.

---

## R6 — The version handshake

### 6.1 Question
Can a handshake with the app version and a hash of the contract schemas detect a mismatch before any data is read?

### 6.2 What was run
The bridge's first line names the protocol, the app version and a hash of the canonical schema of the link's types (`contract_types.py`: 10 roots and `BotChangedEvent`, through `wire_generic.schema_of`). The desk answers with its own; any difference ends the session. Then `r6_sensitivity.py` rebuilt `BotSnapshot` with one change at a time.

```python
mismatch = [k for k in ("protocol", "app_version", "contract_hash") if theirs.get(k) != hello[k]]
if mismatch:
    send({"type": "refused", "reason": "incompatible", "differs": mismatch, "host": hello})
    return 3
```

### 6.3 Result

```text
mismatch: {"type": "refused", "differs": ["contract_hash"], "exit_status": 3}     (6 of 6 runs)

BotSnapshot as built                 9763af3b0165e296
rebuilt, unchanged                   9763af3b0165e296  same
field added (leverage: int)          315fbd8c4af39545  DIFFERS
field renamed (name -> label)        e7b627e79dd63162  DIFFERS
field retyped (symbol: str -> int)   2728257f064a9354  DIFFERS
enum member added (PARKED)           7c29ba3da92dbefa vs 727e95e8351a5f53
```

### 6.4 Verdict and effects
**Confirmed.** A mismatch is detected before any read, refused in words (`differs` names what), and the bridge exits 3. Two findings:
- **Hash the wire names, not the Python names.** The spike's hash names a record by its module and class: building the test, the same fields in a class made in another module gave another hash. Moving a class to another file would refuse every desk with the wire unchanged. The hash should read explicit wire names (`schema` strings such as `sew.bot-snapshot/1`, as `host_command_codec.py` and `health_snapshot.py` already carry), and the same names tag the unions of R4.
- **Charter Scenario 4 needs a decision.** It promises "offers only reading until then" on an older host. One contract hash can only say "same" or "different"; reading safely across versions needs per-type compatibility, which the hand-written file codecs have and the link does not. Recommendation: **v1 refuses the whole link** on any difference and says "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`"; read-only across versions becomes a later variant behind the handshake.

---

## R7 — How large is the "UI around the doors" debt?

### 7.1 Question
On every screen, how many UI imports reach application services, adapters and behavioural ports of other modules, outside the UI-only allowlist? Which presenters receive the whole `IContainer`? The method must be reusable by G9's guard test.

### 7.2 Method (for the guard test)
`scan_ui_doors.py`, read-only, `ast` plus `importlib`:

1. Every `.py` under `src/modules/<m>/ui/` (441 files). Its *screen area* is `<m>/ui/<first directory>`; files directly under `ui/` form `<m>/ui`.
2. Each absolute `from X import N` (and `import X`) whose `X` is inside `src` is classified:
   - **APP_SERVICE**: `X` contains `.application.services.`;
   - **APP_OTHER**: `X` contains `.application.` but is not a use case's message module, `.application.(queries|commands|use_cases).<uc>[.query|.command|.result]` (handlers, kinds, plan documents, setup services);
   - **ADAPTER**: `X` contains `.adapters.` or starts with `src.infrastructure`;
   - **PORT**: `N` is a class in a `contracts` package (of a module, of `core` or of a support package) with a non-empty `__abstractmethods__`, and `N` is not in the allowlist.
3. APP_SERVICE and APP_OTHER hits are split into **fn** (a function or a non-data class: computation the UI runs) and **data** (a dataclass, an enum, a constant).
4. A function with a parameter annotated `IContainer` takes the container; for `__init__`, its class is reported.

Allowlist used: `ICommandDispatcher`, `IEventPublisher`, `IEventBus` (the doors); `INotifier`, `IRealMoneyConsent`, `IThreadManager`, `IInstanceAccess`, `IDisplayTimezonePreference`, `IDisplayPreferences` (UI-only).

```python
USE_CASE_MESSAGE = re.compile(r"\.application\.(queries|commands|use_cases)\.[a-z_0-9]+(\.(query|command|result))?$")

def classify(module: str, name: str | None) -> str | None:
    short = module.removeprefix(PKG)
    if not short.startswith("src."):
        return None
    if ".application.services." in short or short.endswith(".application.services"):
        return "APP_SERVICE"
    if ".adapters." in short or short.endswith(".adapters") or short.startswith("src.infrastructure"):
        return "ADAPTER"
    if ".application." in short and not USE_CASE_MESSAGE.search(short):
        return "APP_OTHER"
    if name and ".contracts" in short and name not in ALLOWED_PORTS:
        obj = getattr(importlib.import_module(module), name)
        if inspect.isclass(obj) and getattr(obj, "__abstractmethods__", None):
            return "PORT"
    return None
```

### 7.3 Result

```text
files scanned: 441
area                          APP_SERVICE  APP_OTHER  ADAPTER  PORT  total   ports: own / other module
alerting/ui/history                     0          1        0     1      2   1 / 0
alerting/ui/options                     0         58        0     7     65   7 / 0
backtesting/ui                          0          1        0     8      9   0 / 8
backtesting/ui/coordinators             0          3        0     8     11   0 / 8
bots/ui/backtest                        0          0        0     1      1   1 / 0
bots/ui/backtest_workbench              0          0        0     7      7   4 / 3
bots/ui/bots_screen                    24          2        2    17     45   7 / 10
bots/ui/chart                           0          0        0     1      1   0 / 1
bots/ui/kinds                           2          2        0     0      4   0 / 0
bots/ui/strategies                      2          0        0     6      8   0 / 6
market_data/ui                          0          0        0     2      2   2 / 0
market_data/ui/coordinators             0         12        0     5     17   5 / 0
market_data/ui/logic                    0          0        0     4      4   4 / 0
trading/ui                              0          1        0     1      2   1 / 0
trading/ui/desk                         0          0        0    20     20  16 / 4
trading/ui/market                       0          0        0    14     14   1 / 13
trading/ui/settings                     0          2        0     0      2   0 / 0
trading/ui/trade                        0          0        0     1      1   1 / 0
ALL                                    28         82        2   103    215  50 / 53

split into fn (computation) / data:
  alerting/ui/history       app other fn 1
  alerting/ui/options       app other fn 14, data 44
  backtesting/ui            app other data 1
  backtesting/ui/coord.     app other fn 2, data 1
  bots/ui/bots_screen       services fn 10, data 14 | app other data 2
  bots/ui/kinds             services fn 2 | app other fn 2
  bots/ui/strategies        services data 2
  market_data/ui/coord.     app other fn 1, data 11
  trading/ui                app other data 1
  trading/ui/settings       app other data 2
```

- **215 bypass imports in 82 files**, spread over 18 screen areas.
- The most imported ports: `IMarketDataSync` 9, `ISymbolCatalog` 8, `IHistoricalKlines` 8, `IBotKind` 8, `ICandleFeed` 6, `IVenueContexts` 5, `IVenueTradingPorts` 4, `ISymbolMetadataProvider` 4, `IMarketDataRepository` 4, `IBotKindCatalog` 4.
- The only **adapter** import: `bots_screen/plan_export_flow.py` writes the plan file itself (`bots.adapters.plan_file` → `write_new_plan_file`, `PlanFileRefused`).
- **30 functions under `ui/` take the whole `IContainer`**: the presenters `AlertsPresenter`, `AlertsSettingsPresenter`, `BackTestPresenter`, `BotsPresenter`, `DataManagementPresenter`, `MarketDataSettingsPresenter`, `DeskPresenter`, `MarketPresenter`, `TradingSettingsPresenter`, `TradePresenter`; the factories and resolvers `build_alerts_presenter`, `build_alerts_options_page`, `display_zone_key_of`, `backtest_screen`, `build_backtest_screen_view`, `build_backtest_screen_presenter`, `bots_dependencies_for`, `new_bot_symbols`, `venue_candles`, `strategies_for`, `build_coordinators`, `build_market_data_options_page`, `desk_dependencies_for`, `venue_key_check`, `market_dependencies_for`, `build_market_presenter`, `build_trading_session_probe`, `build_trading_options_page`, `trade_dependencies_for`, `build_trade_presenter`. The signature is fixed by `screen_descriptor.py` → `ScreenDescriptor.presenter_class` (`(BaseView, IContainer)`).

### 7.4 Verdict and effects on G9
**Measured.** The debt is on every screen, not only Bots, which confirms G9's choice of a separate epic. Inputs for its decision record:
- **Baseline**: 215 imports and 30 container-taking functions, by this method, at 5ddbd68.
- **Allowlist question 1 — pure code ports.** `IBotKind` and `IBotKindCatalog` (12 hits) are the kinds' judges and editors: code, identical on both sides by R6, not host facts. `ICandleFeed` (6 hits) is public market data the charter keeps local. Allowed, the baseline falls by 18 (Bots screen: 17 → 8 ports).
- **Allowlist question 2 — data from the application layer.** 78 of the 110 application imports are data (results, words, enums, constants). The rule can forbid only `fn` imports at first and leave data for a later ratchet.
- The method reports a class's own module's ports as well as another module's (50 / 53); the charter's wording ("of any module other than…") counts both.

---

## 8. Assumptions A6 and A7

### 8.1 A6 — Every query the Bots screen runs can be made asynchronous without changing what it shows
**Holds, with five reads to move.** Eight of the nine query types the screen sends already run on the thread pool: `ListBotsQuery`, `GetExchangeFactsQuery`, `GetPlanRiskFactsQuery`, `GetPlannerMarketQuery`, `GetBotFillsQuery` through `fenced_reads.py:186`; `GetVenueConnectionQuery` through `connect_step.py:272`; `RunBacktestQuery` and `GetStoredCandlesQuery` through the workbench's pool (`backtest_run_coordinator.py:109`, `candle_preview.py:95`). On the UI thread today:

| Read | Where | Remote fix |
|------|-------|------------|
| `ExportBotPlanQuery` | `plan_export_flow.py:142`, synchronous `dispatch` | through the pool, as the others |
| `BotRunFactsReader.read` | `selected_bot.py:196`, on every detail refresh, the 150 ms re-judge included | `GetBotRunFactsQuery`, read with the bot's other facts and kept with them, so a re-judge reads no host |
| each venue's stored key | `venue_choice.py:95` (`credentials_provider.resolve()`) | `GetVenueChoicesQuery`; the key never leaves the host |
| each venue's symbol filters | `bots_dependencies.py:175`, at construction | carried by `PlannerMarket.terms` |
| the strategy rows' wiring | `strategies_wiring.py:45` resolves `IVenueStrategyControls`, `IVenueTradingPorts` and the whole `IConfig` | strategy queries and `ArmedStrategyChangedEvent` (G9's scope) |

What must stay synchronous is the pure re-judge over facts already held (R1, §1.5): it reads no host, so a slow link never delays a keystroke.

### 8.2 A7 — The Bots screen can reach the application only through the dispatcher, the bus and the allowlist, without a visible change
**Likely true.** R1 rendered the detail through the dispatcher alone with no visible change. What stands in the way, from §7.3 for `bots/ui/bots_screen`: 24 application-service imports (10 of them computation, over 8 names: `assess_readiness`, `assess_resume`, `field_verdicts`, `occupancy_of`, `account_view_of`, `state_words`, `failure_cause`, and the `BotRunFactsReader` class), 17 port imports (8 outside the allowlist questions of §7.4: `IVenueContexts` 3, `ISymbolCatalog` 2, `IVenueTradingPorts`, `IMarketDataSources`, `IMarketDataSync`), and the plan file written by the screen itself. Each one has a target in §1.3 or §8.1. The remaining proof is G9's own work, gated by its guard.

---

## 9. Decisions this evidence asks to change

| # | Decision | Change | Why (evidence) | Constitution |
|---|----------|--------|----------------|--------------|
| 1 | **G6** | Reword: every **host fact** reaches the screen through a query or a bus event; the **pure assessment** over those facts leaves `ui/` for the application layer and runs on the desktop. Two new queries: `GetBotRunFactsQuery`, `GetVenueChoicesQuery` | R1: same `BotDetail` from wire-borne facts; the 150 ms re-judge would otherwise be an SSH round trip | P3 (one assessment, used by the desk and the host), P6 |
| 2 | **G7** | Name the shape: the bridge is a **second process** on the host (as `M bot …`), started by `sshd` through a key restricted to it in `sew`'s `authorized_keys`; reads from the store's files and from a facts file the host writes on change; commands through `DirectoryHostControl`; events from the store's writes. Drop "the Docker `dial-stdio` pattern" as the description: Docker dials a listening Unix socket. A Unix socket in `state/` (0600) stays a later variant behind the transport seam, if the ~1 s command latency or the facts file prove insufficient; it needs the owner's decision, as it reverses EPIC-038's "no socket" in spirit (the existing test checks TCP ports only) | R2: no listener, forced command holds; §2.5 table | P8 (EPIC-038's decision kept), P7, P5 |
| 3 | **G7, new requirement** | The host publishes the facts a second process cannot read (symbol leases, enabled venues, budget caps, the exchange facts it already reads) to a file on change; the bridge never calls the exchange itself | §2.5: no other path without a socket; the bridge's own REST calls would share the bots' request weight | P3, real money |
| 4 | **G1** | No change until the owner's run (§R3.4); record the `client_keys=None` trap; the SSH loop runs on its own thread with no blocking call | R3 | P1 |
| 5 | **Link protocol** | A per-bot revision in each record; a desk heartbeat with a bridge-side idle watchdog; the handshake hashes **wire names**; one reflective codec with a contract test per root type | R4, R5, R6 | P1, P8 |
| 6 | **Charter Scenario 4** | v1 refuses the whole link on any version difference, in words naming both builds and `sudo sew-update`; read-only across versions becomes a later variant | R6 | P7 |
| 7 | **G9** | Baseline 215 imports and 30 container-taking functions (§7.2 method); decide the two allowlist questions of §7.4 in its decision record | R7 | P1, P8 |
| 8 | **A1, D6** | A1 is false: the epic's runbook starts with the key setup of §R3.4, and the connection profile (D5) references that key or the agent, never a password | the owner's run, 2026-10-24 | P2, no secret stored by the app (charter §5.1) |

Items 1, 4 and 5 are within the delegation that settled G1–G9: reversible, no real-money behaviour, no dependency. Items 2, 3 and 6 change what the owner reads in the charter and touch the host's behaviour, so they are put to the owner with the decision records; nothing is built until then.

---

## Sources
- OpenSSH `sshd(8)`, `AUTHORIZED_KEYS FILE FORMAT` (`command=`, `restrict`): <https://man.openbsd.org/sshd#AUTHORIZED_KEYS_FILE_FORMAT>
- Docker `docker system dial-stdio` and the SSH connection helper: <https://docs.docker.com/engine/security/protect-access/>
- AsyncSSH, `connect()` options (`client_keys`, `agent_path`, `known_hosts`): <https://asyncssh.readthedocs.io/en/latest/api.html#connect>
- Paramiko `SSHClient.connect` and `RejectPolicy`: <https://docs.paramiko.org/en/stable/api/client.html>
- Home Assistant WebSocket API (correlation ids, subscribe): <https://developers.home-assistant.io/docs/api/websocket>
